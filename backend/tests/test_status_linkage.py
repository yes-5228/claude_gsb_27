"""开放状态联动测试：巡查任务、整改期限顺延、漏检统计与月度考核。"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from tests.conftest import full_items


def _change_status(client, restroom_id, to_status, reason="测试变更", operator="值班长"):
    response = client.post(
        f"/api/v1/restrooms/{restroom_id}/status",
        json={"to_status": to_status, "reason": reason, "operator": operator},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _tasks_today(client, restroom_id):
    payload = client.get(
        "/api/v1/inspection-tasks", params={"restroom_id": restroom_id}
    ).json()
    return payload["items"]


def test_status_change_traced_and_inspection_gated(client, restroom):
    rid = restroom["id"]

    # 停用与恢复都留痕
    _change_status(client, rid, "维修中", reason="化粪池检修")
    _change_status(client, rid, "暂停使用", reason="道路施工")
    _change_status(client, rid, "正常开放", reason="施工结束")

    events = client.get(f"/api/v1/restrooms/{rid}/status-events").json()
    assert [event["to_status"] for event in events] == ["维修中", "暂停使用", "正常开放"]
    assert events[0]["from_status"] == "正常开放"
    assert events[0]["reason"] == "化粪池检修"
    assert events[0]["operator"] == "值班长"

    detail = client.get(f"/api/v1/restrooms/{rid}").json()
    assert detail["status_changed_at"] is not None

    # 重复变更到相同状态被拒绝
    same = client.post(
        f"/api/v1/restrooms/{rid}/status",
        json={"to_status": "正常开放", "reason": "重复操作", "operator": "值班长"},
    )
    assert same.status_code == 400

    # 转维修后不再生成巡查记录
    _change_status(client, rid, "维修中", reason="更换水箱")
    blocked = client.post(
        "/api/v1/inspections",
        json={"restroom_id": rid, "inspector": "李巡查", "items": full_items(9)},
    )
    assert blocked.status_code == 400
    assert "停用期间不生成巡查任务" in blocked.json()["detail"]

    # 停用前开放时段的历史巡查仍允许补录
    backfill = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": rid,
            "inspector": "李巡查",
            "items": full_items(9),
            "inspect_time": (datetime.now() - timedelta(hours=1)).isoformat(),
        },
    )
    assert backfill.status_code == 201

    # 恢复开放后可以正常巡查
    _change_status(client, rid, "正常开放", reason="维修完成")
    ok = client.post(
        "/api/v1/inspections",
        json={"restroom_id": rid, "inspector": "李巡查", "items": full_items(9)},
    )
    assert ok.status_code == 201


def test_tasks_cancel_and_restore_without_duplicates(client, restroom):
    rid = restroom["id"]
    today = date.today().isoformat()

    created = client.post("/api/v1/inspection-tasks/generate", json={"task_date": today}).json()
    assert created["created"] >= 1
    # 重复生成不重复
    again = client.post("/api/v1/inspection-tasks/generate", json={"task_date": today}).json()
    assert again["created"] == 0

    tasks = _tasks_today(client, rid)
    assert len(tasks) == 1 and tasks[0]["status"] == "待执行"

    # 转维修：待执行任务被取消
    result = _change_status(client, rid, "维修中", reason="停水检修")
    assert result["cancelled_tasks"] == 1
    tasks = _tasks_today(client, rid)
    assert len(tasks) == 1 and tasks[0]["status"] == "已取消"
    assert "停水检修" in tasks[0]["cancel_reason"]

    # 短时间内反复切换：任务不重复、不漏项
    _change_status(client, rid, "正常开放", reason="恢复供水")
    _change_status(client, rid, "暂停使用", reason="临时管制")
    _change_status(client, rid, "正常开放", reason="解除管制")
    tasks = _tasks_today(client, rid)
    assert len(tasks) == 1
    assert tasks[0]["status"] == "待执行"
    assert tasks[0]["cancel_reason"] is None

    events = client.get(f"/api/v1/restrooms/{rid}/status-events").json()
    assert len(events) == 4

    # 提交巡查后任务自动完成
    inspection = client.post(
        "/api/v1/inspections",
        json={"restroom_id": rid, "inspector": "李巡查", "items": full_items(9)},
    )
    assert inspection.status_code == 201
    tasks = _tasks_today(client, rid)
    assert tasks[0]["status"] == "已完成"
    assert tasks[0]["inspection_id"] == inspection.json()["id"]


def test_task_display_missed_for_past_pending(client, restroom):
    rid = restroom["id"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post("/api/v1/inspection-tasks/generate", json={"task_date": yesterday})

    payload = client.get(
        "/api/v1/inspection-tasks",
        params={"task_date": yesterday, "restroom_id": rid},
    ).json()
    assert payload["meta"]["total"] == 1
    task = payload["items"][0]
    assert task["status"] == "待执行"
    assert task["display_status"] == "漏检"

    filtered = client.get(
        "/api/v1/inspection-tasks",
        params={"task_date": yesterday, "restroom_id": rid, "status": "漏检"},
    ).json()
    assert filtered["meta"]["total"] == 1


def test_deadline_extension_by_rule(client, restroom):
    rid = restroom["id"]
    past = (datetime.now() - timedelta(days=1)).isoformat()

    # 生效时间在未来：不参与判定
    future_rule = client.post(
        "/api/v1/deadline-rules",
        json={
            "name": "未来规则",
            "extend_days": 30,
            "trigger_statuses": ["维修中"],
            "effective_from": (datetime.now() + timedelta(days=7)).isoformat(),
        },
    )
    assert future_rule.status_code == 201

    rule = client.post(
        "/api/v1/deadline-rules",
        json={
            "name": "维修顺延3天",
            "extend_days": 3,
            "trigger_statuses": ["维修中", "暂停使用"],
            "effective_from": past,
            "remark": "停用期间整改期限自动顺延",
        },
    )
    assert rule.status_code == 201, rule.text

    deadline = datetime.now() + timedelta(days=1)
    issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": rid,
            "title": "水龙头损坏",
            "category": "设施损坏",
            "deadline": deadline.isoformat(),
        },
    ).json()

    # 开放 -> 维修中：按规则顺延 3 天并说明原因
    result = _change_status(client, rid, "维修中", reason="内部改造")
    assert result["extended_issues"] == 1
    assert result["applied_rule"] == "维修顺延3天"

    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    new_deadline = datetime.fromisoformat(detail["deadline"])
    assert abs((new_deadline - (deadline + timedelta(days=3))).total_seconds()) < 2
    extension = detail["records"][-1]
    assert extension["action"] == "期限顺延"
    assert "维修顺延3天" in extension["remark"]
    assert "顺延 3 天" in extension["remark"]

    # 维修中 -> 暂停使用：同为停用，不重复顺延
    _change_status(client, rid, "暂停使用", reason="改造升级")
    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    assert abs((datetime.fromisoformat(detail["deadline"]) - new_deadline).total_seconds()) < 2

    # 恢复后再停用：新的停用 episode 再次顺延
    _change_status(client, rid, "正常开放", reason="改造完成")
    _change_status(client, rid, "维修中", reason="二次维修")
    detail = client.get(f"/api/v1/issues/{issue['id']}").json()
    expected = deadline + timedelta(days=6)
    assert abs((datetime.fromisoformat(detail["deadline"]) - expected).total_seconds()) < 2

    # 规则停用后不再顺延
    client.patch(f"/api/v1/deadline-rules/{rule.json()['id']}", json={"enabled": False})
    _change_status(client, rid, "正常开放", reason="维修完成")
    result = _change_status(client, rid, "维修中", reason="三次维修")
    assert result["extended_issues"] == 0
    assert result["applied_rule"] is None
    _change_status(client, rid, "正常开放", reason="维修完成")


def test_open_dates_pure_logic():
    """应巡判定：停用当日空白不算漏检，反复切换不重复计算。"""
    from app.services.status_service import open_dates, status_at

    created = datetime(2026, 9, 1, 8, 0, 0)
    events = [
        SimpleNamespace(
            created_at=datetime(2026, 9, 10, 9, 0), from_status="正常开放", to_status="维修中"
        ),
        SimpleNamespace(
            created_at=datetime(2026, 9, 10, 18, 0), from_status="维修中", to_status="正常开放"
        ),
        SimpleNamespace(
            created_at=datetime(2026, 9, 12, 0, 0), from_status="正常开放", to_status="暂停使用"
        ),
    ]
    days = open_dates(events, "暂停使用", created, date(2026, 9, 1), date(2026, 9, 15))
    # 9-1 ~ 9-11 开放过（9-10 当天反复切换仍只算 1 天），9-12 起全天停用
    assert days == {date(2026, 9, d) for d in range(1, 12)}
    # 建档日以前不算应巡
    assert date(2026, 8, 31) not in open_dates(events, "暂停使用", created, date(2026, 8, 28), date(2026, 9, 2))
    # 时刻状态推算
    assert status_at(datetime(2026, 9, 10, 12, 0), events, "暂停使用") == "维修中"
    assert status_at(datetime(2026, 9, 13, 12, 0), events, "暂停使用") == "暂停使用"
    assert status_at(datetime(2026, 9, 1, 0, 0), events, "暂停使用") == "正常开放"
    # 无流水时以当前状态为准
    assert status_at(datetime(2026, 9, 1), [], "维修中") == "维修中"


def test_dashboard_exposes_missed_and_closed(client, restroom):
    payload = client.get("/api/v1/stats/dashboard", params={"trend_days": 7}).json()
    overview = payload["overview"]
    assert "inspection_missed_week" in overview
    assert "restroom_closed" in overview
    assert all("missed" in point for point in payload["inspection_trend"])


def test_monthly_assessment_frozen_once_issued(client, restroom):
    rid = restroom["id"]
    month = datetime.now().strftime("%Y-%m")

    first = client.post("/api/v1/assessments/generate", json={"month": month}).json()
    assert first["created"] >= 1
    assert first["skipped"] == 0

    # 已生成的月份不重复生成
    second = client.post("/api/v1/assessments/generate", json={"month": month}).json()
    assert second["created"] == 0
    assert second["skipped"] >= 1

    mine = client.get("/api/v1/assessments", params={"month": month, "page_size": 100}).json()
    target = next(item for item in mine["items"] if item["restroom_id"] == rid)
    snapshot = (target["expected_count"], target["missed_count"], target["result"])

    # 已出的月度考核不随状态切换改变
    _change_status(client, rid, "维修中", reason="考核后停用")
    client.post("/api/v1/assessments/generate", json={"month": month})
    mine = client.get("/api/v1/assessments", params={"month": month, "page_size": 100}).json()
    target = next(item for item in mine["items"] if item["restroom_id"] == rid)
    assert (target["expected_count"], target["missed_count"], target["result"]) == snapshot
    _change_status(client, rid, "正常开放", reason="恢复开放")

    # 未来月份不允许生成
    future = client.post("/api/v1/assessments/generate", json={"month": "2099-01"})
    assert future.status_code == 400
