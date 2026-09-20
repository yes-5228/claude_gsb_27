"""状态联动测试：转维修/暂停与巡查、整改期限、漏检统计、月度考核的联动。"""

from datetime import datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models import DeadlineExtensionRule, SuspensionPeriod
from tests.conftest import full_items


@pytest.fixture(autouse=True)
def _clean_rules(client):
    """每个用例前清空顺延规则，避免规则跨用例残留影响判定。"""
    db = SessionLocal()
    try:
        db.query(DeadlineExtensionRule).delete()
        db.commit()
    finally:
        db.close()
    yield


def _db():
    return SessionLocal()


def _make_issue(client, restroom_id, *, deadline):
    response = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom_id,
            "title": "设施损坏待维修",
            "category": "设施损坏",
            "severity": "严重",
            "reporter": "巡查员",
            "assignee": "维修班",
            "deadline": deadline.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _change_status(client, restroom_id, to_status, reason="现场需要", operator="值班长"):
    response = client.post(
        f"/api/v1/restrooms/{restroom_id}/status",
        json={"to_status": to_status, "reason": reason, "operator": operator},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_rule(client, *, effective_from, extend_days, note="测试规则"):
    response = client.post(
        "/api/v1/rules/deadline-extensions",
        json={
            "effective_from": effective_from.isoformat(),
            "extend_days": extend_days,
            "note": note,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_suspend_blocks_new_inspection(client, restroom):
    _change_status(client, restroom["id"], "维修中", "水管爆裂")
    blocked = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "巡查员", "items": full_items(9)},
    )
    assert blocked.status_code == 400
    assert "停用" in blocked.json()["detail"]

    # 恢复开放后可以重新登记巡查
    _change_status(client, restroom["id"], "正常开放", "维修完成")
    allowed = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "巡查员", "items": full_items(9)},
    )
    assert allowed.status_code == 201


def test_status_change_leaves_audit_trail(client, restroom):
    _change_status(client, restroom["id"], "暂停使用", "道路施工", "张三")
    _change_status(client, restroom["id"], "正常开放", "施工结束", "李四")

    events = client.get(f"/api/v1/restrooms/{restroom['id']}/status-events").json()
    assert len(events) == 2
    # 停用与恢复都留痕，按时间倒序
    assert events[0]["to_status"] == "正常开放"
    assert events[0]["operator"] == "李四"
    assert events[1]["to_status"] == "暂停使用"
    assert events[1]["from_status"] == "正常开放"
    assert events[1]["reason"] == "道路施工"

    suspensions = client.get(f"/api/v1/restrooms/{restroom['id']}/suspensions").json()
    assert len(suspensions) == 1
    assert suspensions[0]["started_at"] is not None
    assert suspensions[0]["ended_at"] is not None  # 已恢复，区间关闭


def test_resume_extends_open_issue_deadline(client, restroom):
    _create_rule(
        client,
        effective_from=datetime.now() - timedelta(days=1),
        extend_days=3,
        note="停用固定顺延 3 天",
    )
    deadline = datetime.now() + timedelta(days=1)
    issue = _make_issue(client, restroom["id"], deadline=deadline)

    _change_status(client, restroom["id"], "维修中", "整体翻新")
    result = _change_status(client, restroom["id"], "正常开放", "翻新完成")
    assert result["extended_issue_count"] == 1

    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    new_deadline = datetime.fromisoformat(detail["deadline"])
    expected = deadline + timedelta(days=3)
    assert abs((new_deadline - expected).total_seconds()) < 2

    # 整改流水里有顺延说明
    actions = [record["action"] for record in detail["records"]]
    assert "期限顺延" in actions
    extension = next(r for r in detail["records"] if r["action"] == "期限顺延")
    assert "顺延" in extension["remark"]


def test_extension_rule_effective_time(client, restroom):
    # 未来才生效的规则不影响当前停用判定
    _create_rule(
        client,
        effective_from=datetime.now() + timedelta(days=1),
        extend_days=5,
        note="未来生效",
    )
    deadline = datetime.now() + timedelta(days=1)
    issue = _make_issue(client, restroom["id"], deadline=deadline)

    _change_status(client, restroom["id"], "维修中", "检修")
    _change_status(client, restroom["id"], "正常开放", "检修完成")
    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    assert abs((datetime.fromisoformat(detail["deadline"]) - deadline).total_seconds()) < 2

    # 已生效的规则会影响此后的判定
    _create_rule(
        client,
        effective_from=datetime.now() - timedelta(days=1),
        extend_days=2,
        note="即时生效",
    )
    _change_status(client, restroom["id"], "维修中", "二次检修")
    _change_status(client, restroom["id"], "正常开放", "二次检修完成")
    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    expected = deadline + timedelta(days=2)
    assert abs((datetime.fromisoformat(detail["deadline"]) - expected).total_seconds()) < 2


def test_repeated_toggle_no_duplicate_extension(client, restroom):
    _create_rule(
        client,
        effective_from=datetime.now() - timedelta(days=1),
        extend_days=2,
        note="固定顺延 2 天",
    )
    deadline = datetime.now() + timedelta(days=1)
    issue = _make_issue(client, restroom["id"], deadline=deadline)

    # 短时间内反复切换：每次停用区间独立结算，不重复也不漏项
    for _ in range(2):
        _change_status(client, restroom["id"], "维修中", "反复切换")
        _change_status(client, restroom["id"], "正常开放", "恢复")

    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    expected = deadline + timedelta(days=4)  # 两段区间各顺延 2 天
    assert abs((datetime.fromisoformat(detail["deadline"]) - expected).total_seconds()) < 2
    extensions = [r for r in detail["records"] if r["action"] == "期限顺延"]
    assert len(extensions) == 2

    suspensions = client.get(f"/api/v1/restrooms/{restroom['id']}/suspensions").json()
    assert len(suspensions) == 2
    assert all(p["extension_settled"] for p in suspensions)


def _backdate_suspension(restroom_id, start, end):
    db = _db()
    try:
        db.add(
            SuspensionPeriod(
                restroom_id=restroom_id,
                started_at=start,
                ended_at=end,
                reason="历史停用",
                operator="测试员",
                extend_days=None,
                extension_settled=True,
            )
        )
        db.commit()
    finally:
        db.close()


def _assessment_for(client, restroom_id, year_month):
    rows = client.get("/api/v1/stats/assessments", params={"year_month": year_month}).json()
    return next((row for row in rows if row["restroom_id"] == restroom_id), None)


def test_suspension_not_counted_as_missed(client, restroom):
    rid = restroom["id"]
    # 整座公厕 2020-01 全月停用：应巡为 0，停用空白不算漏巡
    _backdate_suspension(rid, datetime(2020, 1, 1), datetime(2020, 2, 1))
    client.post("/api/v1/stats/assessments/generate", json={"year_month": "2020-01"})
    row = _assessment_for(client, rid, "2020-01")
    assert row is not None
    assert row["open_days"] == 0
    assert row["expected_inspections"] == 0
    assert row["missed_inspections"] == 0


def test_full_open_month_counts_expected(client, restroom):
    rid = restroom["id"]
    # 无停用的完整月份：应巡 = 开放天数 × 每日定额，未巡查则全部计为漏巡
    client.post("/api/v1/stats/assessments/generate", json={"year_month": "2020-02"})
    row = _assessment_for(client, rid, "2020-02")
    assert row is not None
    assert row["open_days"] == 29  # 2020 年 2 月
    assert row["expected_inspections"] == 29 * 2
    assert row["actual_inspections"] == 0
    assert row["missed_inspections"] == 29 * 2


def test_monthly_assessment_frozen_after_generated(client, restroom):
    rid = restroom["id"]
    first = client.post("/api/v1/stats/assessments/generate", json={"year_month": "2021-05"})
    assert first.json()["generated"] >= 1
    before = _assessment_for(client, rid, "2021-05")
    assert before is not None

    # 之后发生状态变化与巡查，已出的月度考核不跟着变
    _change_status(client, rid, "维修中", "考核后停用")
    _change_status(client, rid, "正常开放", "考核后恢复")
    again = client.post("/api/v1/stats/assessments/generate", json={"year_month": "2021-05"})
    assert again.json()["generated"] == 0
    assert again.json()["skipped"] >= 1

    after = _assessment_for(client, rid, "2021-05")
    assert after["expected_inspections"] == before["expected_inspections"]
    assert after["missed_inspections"] == before["missed_inspections"]
    assert after["generated_at"] == before["generated_at"]


def test_suspended_status_switch_reuses_period(client, restroom):
    # 维修中 <-> 暂停使用 仍属停用，复用同一区间，不重置停用时钟
    _change_status(client, restroom["id"], "维修中", "检修")
    _change_status(client, restroom["id"], "暂停使用", "叠加施工")
    _change_status(client, restroom["id"], "正常开放", "全部完成")

    suspensions = client.get(f"/api/v1/restrooms/{restroom['id']}/suspensions").json()
    assert len(suspensions) == 1  # 只开一段区间
    assert suspensions[0]["ended_at"] is not None

    events = client.get(f"/api/v1/restrooms/{restroom['id']}/status-events").json()
    # 三次变更都留痕
    assert len(events) == 3
    assert [e["to_status"] for e in events] == ["正常开放", "暂停使用", "维修中"]


def test_overview_has_missed_count(client, restroom):
    overview = client.get("/api/v1/stats/overview").json()
    assert "inspection_missed_this_month" in overview
    assert overview["inspection_missed_this_month"] >= 0
