"""月度考核业务逻辑：按自然月生成快照，发布后固化不再变化。"""

import calendar
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    ASSESSMENT_MISSED_PENALTY,
    ASSESSMENT_RESULT_NONE,
    GRADE_EXCELLENT,
    GRADE_FAIL,
    GRADE_GOOD,
    GRADE_PASS,
)
from app.core.exceptions import DomainError
from app.models import Inspection, Issue, MonthlyAssessment, Restroom
from app.services import status_service


def parse_month(month: str) -> tuple[date, date]:
    """把 2026-09 解析为月份起止日期。"""
    try:
        year, mon = int(month[:4]), int(month[5:7])
        last_day = calendar.monthrange(year, mon)[1]
    except (ValueError, IndexError):
        raise DomainError(f"考核月份格式不正确：{month}，应为 YYYY-MM") from None
    return date(year, mon, 1), date(year, mon, last_day)


def _capped_range(month: str) -> tuple[date, date]:
    """考核统计区间：当月只统计到昨天为止，未来月份不允许生成。"""
    start, end = parse_month(month)
    yesterday = datetime.now().date() - timedelta(days=1)
    if start > yesterday:
        raise DomainError(f"月份 {month} 尚未结束，暂不能生成考核")
    return start, min(end, yesterday)


def _result_of(score: float, expected: int) -> str:
    if expected == 0:
        return ASSESSMENT_RESULT_NONE
    if score >= 90:
        return GRADE_EXCELLENT
    if score >= 80:
        return GRADE_GOOD
    if score >= 70:
        return GRADE_PASS
    return GRADE_FAIL


def compute_snapshot(db: Session, restroom: Restroom, start: date, end: date) -> dict:
    """计算一座公厕在 [start, end] 内的考核指标。"""
    open_days = status_service.open_days_for(db, restroom, start, end)
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)

    inspected_days: set[date] = set()
    actual = 0
    score_sum = 0.0
    rows = db.execute(
        select(Inspection.inspect_time, Inspection.score).where(
            Inspection.restroom_id == restroom.id,
            Inspection.inspect_time >= start_dt,
            Inspection.inspect_time <= end_dt,
        )
    ).all()
    for inspect_time, score in rows:
        actual += 1
        score_sum += float(score or 0)
        inspected_days.add(inspect_time.date())

    expected = len(open_days)
    missed = sum(1 for day in open_days if day not in inspected_days)
    avg_score = round(score_sum / actual, 1) if actual else None
    base = avg_score or 0.0
    score = round(max(0.0, base - ASSESSMENT_MISSED_PENALTY * missed), 1) if expected else 0.0

    issue_new = db.scalar(
        select(func.count())
        .select_from(Issue)
        .where(
            Issue.restroom_id == restroom.id,
            Issue.report_time >= start_dt,
            Issue.report_time <= end_dt,
        )
    ) or 0
    issue_closed = db.scalar(
        select(func.count())
        .select_from(Issue)
        .where(
            Issue.restroom_id == restroom.id,
            Issue.closed_at.is_not(None),
            Issue.closed_at >= start_dt,
            Issue.closed_at <= end_dt,
        )
    ) or 0

    return {
        "expected_count": expected,
        "actual_count": actual,
        "missed_count": missed,
        "avg_score": avg_score,
        "issue_new": issue_new,
        "issue_closed": issue_closed,
        "score": score,
        "result": _result_of(score, expected),
    }


def generate(db: Session, month: str, operator: str = "系统") -> tuple[int, int]:
    """为全部公厕生成指定月份的考核快照；已生成的跳过，保证不重复、不覆盖。"""
    start, end = _capped_range(month)
    existing = set(
        db.scalars(select(MonthlyAssessment.restroom_id).where(MonthlyAssessment.month == month))
    )
    created = 0
    skipped = 0
    for restroom in db.scalars(select(Restroom).order_by(Restroom.id)):
        if restroom.id in existing:
            skipped += 1
            continue
        snapshot = compute_snapshot(db, restroom, start, end)
        db.add(
            MonthlyAssessment(
                restroom_id=restroom.id,
                month=month,
                operator=operator,
                **snapshot,
            )
        )
        created += 1
    if created:
        db.commit()
    return created, skipped


def list_assessments(
    db: Session,
    *,
    month: str | None = None,
    district: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[MonthlyAssessment], int]:
    stmt = select(MonthlyAssessment)
    if month:
        stmt = stmt.where(MonthlyAssessment.month == month)
    if district:
        stmt = stmt.join(Restroom, Restroom.id == MonthlyAssessment.restroom_id).where(
            Restroom.district == district
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(
        MonthlyAssessment.month.desc(), MonthlyAssessment.result, MonthlyAssessment.id
    )
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total
