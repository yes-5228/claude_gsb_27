"""公厕状态联动业务逻辑：状态变更留痕、停用区间、整改期限顺延与月度考核。

联动规则：
- 正常开放 -> 维修中/暂停使用：开启停用区间，按当时生效的顺延规则快照决策；
- 维修中/暂停使用 -> 正常开放：关闭停用区间，并按快照决策对未闭环问题结算顺延；
- 维修中 <-> 暂停使用：仍属停用，复用当前区间，仅留痕。
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    INSPECTIONS_DUE_PER_DAY,
    OPEN_ISSUE_STATUSES,
    RESTROOM_STATUS_TRANSITIONS,
    RestroomStatus,
    is_suspended_status,
)
from app.core.exceptions import DomainError, NotFoundError
from app.models import (
    DeadlineExtensionRule,
    Inspection,
    Issue,
    IssueDeadlineExtension,
    MonthlyAssessment,
    RectificationRecord,
    Restroom,
    RestroomStatusEvent,
    SuspensionPeriod,
)
from app.schemas.status_linkage import (
    AssessmentGenerateResult,
    DeadlineExtensionRuleCreate,
    MonthlyAssessmentOut,
    StatusChangeResult,
)


def _get_restroom(db: Session, restroom_id: int) -> Restroom:
    restroom = db.get(Restroom, restroom_id)
    if restroom is None:
        raise NotFoundError(f"公厕 {restroom_id} 不存在")
    return restroom


# ---------------------------------------------------------------------------
# 顺延规则
# ---------------------------------------------------------------------------

def create_rule(db: Session, payload: DeadlineExtensionRuleCreate) -> DeadlineExtensionRule:
    rule = DeadlineExtensionRule(
        effective_from=payload.effective_from,
        extend_days=payload.extend_days,
        note=payload.note,
        active=payload.active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session) -> list[DeadlineExtensionRule]:
    stmt = select(DeadlineExtensionRule).order_by(
        DeadlineExtensionRule.effective_from.desc(), DeadlineExtensionRule.id.desc()
    )
    return list(db.scalars(stmt))


def current_rule(db: Session, at: datetime) -> DeadlineExtensionRule | None:
    """取指定时点生效的最新一条顺延规则（只影响生效之后的判定）。"""
    stmt = (
        select(DeadlineExtensionRule)
        .where(
            DeadlineExtensionRule.active.is_(True),
            DeadlineExtensionRule.effective_from <= at,
        )
        .order_by(DeadlineExtensionRule.effective_from.desc(), DeadlineExtensionRule.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


# ---------------------------------------------------------------------------
# 状态变更联动
# ---------------------------------------------------------------------------

def _open_period(db: Session, restroom_id: int) -> SuspensionPeriod | None:
    """当前未关闭的停用区间（同一时间至多一段）。"""
    stmt = (
        select(SuspensionPeriod)
        .where(
            SuspensionPeriod.restroom_id == restroom_id,
            SuspensionPeriod.ended_at.is_(None),
        )
        .order_by(SuspensionPeriod.started_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _decide_extend_days(db: Session, at: datetime) -> int | None:
    """停用开启时按当时生效的规则快照顺延决策；无规则则不顺延。"""
    rule = current_rule(db, at)
    return rule.extend_days if rule is not None else None


def _settle_extensions(db: Session, period: SuspensionPeriod, resumed_at: datetime) -> int:
    """恢复开放时结算顺延：对未闭环且有期限的问题顺延期限并留痕，幂等。"""
    if period.extend_days is None or period.extension_settled:
        return 0

    if period.extend_days > 0:
        delta = timedelta(days=period.extend_days)
        extend_desc = f"固定顺延 {period.extend_days} 天"
    else:
        delta = resumed_at - period.started_at
        extend_desc = f"按实际停用时长顺延 {delta.total_seconds() / 86400:.1f} 天"
    if delta.total_seconds() <= 0:
        period.extension_settled = True
        return 0

    issues = list(
        db.scalars(
            select(Issue).where(
                Issue.restroom_id == period.restroom_id,
                Issue.status.in_(OPEN_ISSUE_STATUSES),
                Issue.deadline.is_not(None),
            )
        )
    )
    count = 0
    for issue in issues:
        # 同一区间对同一问题只顺延一次
        exists = db.scalar(
            select(IssueDeadlineExtension.id).where(
                IssueDeadlineExtension.issue_id == issue.id,
                IssueDeadlineExtension.suspension_period_id == period.id,
            )
        )
        if exists:
            continue
        old_deadline = issue.deadline
        new_deadline = old_deadline + delta
        reason = (
            f"公厕「{period.reason or '停用'}」期间暂停整改，{extend_desc}，"
            f"期限由 {old_deadline:%Y-%m-%d %H:%M} 顺延至 {new_deadline:%Y-%m-%d %H:%M}"
        )
        issue.deadline = new_deadline
        db.add(
            IssueDeadlineExtension(
                issue_id=issue.id,
                suspension_period_id=period.id,
                old_deadline=old_deadline,
                new_deadline=new_deadline,
                days=delta.total_seconds() / 86400,
                reason=reason,
            )
        )
        issue.records.append(
            RectificationRecord(
                action="期限顺延",
                from_status=issue.status,
                to_status=issue.status,
                operator=period.operator or "系统",
                remark=reason,
            )
        )
        count += 1

    period.extension_settled = True
    return count


def change_restroom_status(
    db: Session,
    restroom_id: int,
    *,
    to_status: str,
    reason: str | None = None,
    operator: str = "",
) -> StatusChangeResult:
    """变更公厕开放状态，并联动停用区间与整改期限顺延。"""
    restroom = _get_restroom(db, restroom_id)
    target = to_status.value if hasattr(to_status, "value") else str(to_status)
    from_status = restroom.status
    if target == from_status:
        raise DomainError(f"公厕已处于「{from_status}」状态")
    allowed = RESTROOM_STATUS_TRANSITIONS.get(from_status, [])
    if target not in allowed:
        raise DomainError(
            f"当前状态「{from_status}」不允许变更为「{target}」，"
            "可选：" + ("、".join(allowed) if allowed else "无")
        )

    now = datetime.now()
    was_suspended = is_suspended_status(from_status)
    will_suspended = is_suspended_status(target)

    event = RestroomStatusEvent(
        restroom_id=restroom.id,
        from_status=from_status,
        to_status=target,
        reason=reason,
        operator=operator,
        created_at=now,
    )
    db.add(event)

    period_id: int | None = None
    extended = 0
    message = ""
    if not was_suspended and will_suspended:
        # 正常 -> 停用：开启停用区间，快照顺延决策，之后不再生成新巡查任务
        period = SuspensionPeriod(
            restroom_id=restroom.id,
            started_at=now,
            reason=reason,
            operator=operator,
            extend_days=_decide_extend_days(db, now),
        )
        db.add(period)
        db.flush()
        period_id = period.id
        message = "已转入停用，停用期间不再生成新的巡查任务"
    elif was_suspended and not will_suspended:
        # 停用 -> 正常：关闭区间并结算顺延
        period = _open_period(db, restroom.id)
        if period is not None:
            period.ended_at = now
            extended = _settle_extensions(db, period, now)
            period_id = period.id
        message = "已恢复开放" + (f"，顺延 {extended} 个未闭环问题的整改期限" if extended else "")
    else:
        # 停用 -> 停用（维修中 <-> 暂停使用）：复用当前区间，仅留痕
        period = _open_period(db, restroom.id)
        period_id = period.id if period is not None else None
        message = "状态已变更，仍处于停用区间"

    restroom.status = target
    restroom.updated_at = now
    db.commit()
    db.refresh(event)
    return StatusChangeResult(
        restroom_id=restroom.id,
        from_status=from_status,
        to_status=target,
        event_id=event.id,
        suspension_period_id=period_id,
        extended_issue_count=extended,
        message=message,
    )


def list_status_events(db: Session, restroom_id: int) -> list[RestroomStatusEvent]:
    _get_restroom(db, restroom_id)
    stmt = (
        select(RestroomStatusEvent)
        .where(RestroomStatusEvent.restroom_id == restroom_id)
        .order_by(RestroomStatusEvent.created_at.desc(), RestroomStatusEvent.id.desc())
    )
    return list(db.scalars(stmt))


def list_suspensions(db: Session, restroom_id: int) -> list[SuspensionPeriod]:
    _get_restroom(db, restroom_id)
    stmt = (
        select(SuspensionPeriod)
        .where(SuspensionPeriod.restroom_id == restroom_id)
        .order_by(SuspensionPeriod.started_at.desc(), SuspensionPeriod.id.desc())
    )
    return list(db.scalars(stmt))


# ---------------------------------------------------------------------------
# 漏检统计与月度考核
# ---------------------------------------------------------------------------

def _suspended_seconds(
    periods: list[SuspensionPeriod], start: datetime, end: datetime, now: datetime
) -> float:
    """停用区间与 [start, end) 求交的总时长（秒），区间不重叠，直接累加。"""
    total = 0.0
    for period in periods:
        p_start = max(period.started_at, start)
        p_end = min(period.ended_at or now, end)
        if p_end > p_start:
            total += (p_end - p_start).total_seconds()
    return total


def month_bounds(year_month: str) -> tuple[datetime, datetime]:
    """把 2026-09 解析为该月起止时间。"""
    try:
        start = datetime.strptime(year_month, "%Y-%m")
    except ValueError as exc:
        raise DomainError(f"月份格式应为 YYYY-MM，收到：{year_month}") from exc
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _periods_by_restroom(db: Session, start: datetime, end: datetime) -> dict[int, list]:
    stmt = select(SuspensionPeriod).where(
        SuspensionPeriod.started_at < end,
        (SuspensionPeriod.ended_at.is_(None)) | (SuspensionPeriod.ended_at > start),
    )
    grouped: dict[int, list[SuspensionPeriod]] = {}
    for period in db.scalars(stmt):
        grouped.setdefault(period.restroom_id, []).append(period)
    return grouped


def missed_inspection_count(db: Session, start: datetime, end: datetime) -> int:
    """统计 [start, end) 范围内的漏巡次数：应巡查按开放天数折算，停用期间不计。"""
    now = datetime.now()
    end = min(end, now)
    if end <= start:
        return 0
    total_seconds = (end - start).total_seconds()
    periods_map = _periods_by_restroom(db, start, end)

    expected = 0
    restrooms = list(db.scalars(select(Restroom)))
    for restroom in restrooms:
        suspended = _suspended_seconds(periods_map.get(restroom.id, []), start, end, now)
        open_seconds = max(0.0, total_seconds - suspended)
        open_days = open_seconds / 86400
        expected += open_days * INSPECTIONS_DUE_PER_DAY

    actual = db.scalar(
        select(func.count())
        .select_from(Inspection)
        .where(Inspection.inspect_time >= start, Inspection.inspect_time < end)
    ) or 0
    return max(0, math.floor(expected) - actual)


def generate_assessments(db: Session, year_month: str) -> AssessmentGenerateResult:
    """生成指定月份的月度考核快照；已生成的公厕跳过，不回溯修改。"""
    start, end = month_bounds(year_month)
    now = datetime.now()
    periods_map = _periods_by_restroom(db, start, end)
    total_seconds = (end - start).total_seconds()

    generated = 0
    skipped = 0
    for restroom in db.scalars(select(Restroom)):
        exists = db.scalar(
            select(MonthlyAssessment.id).where(
                MonthlyAssessment.restroom_id == restroom.id,
                MonthlyAssessment.year_month == year_month,
            )
        )
        if exists:
            skipped += 1
            continue

        suspended = _suspended_seconds(periods_map.get(restroom.id, []), start, end, now)
        open_days = max(0, round((total_seconds - suspended) / 86400))
        expected = open_days * INSPECTIONS_DUE_PER_DAY
        actual = db.scalar(
            select(func.count())
            .select_from(Inspection)
            .where(
                Inspection.restroom_id == restroom.id,
                Inspection.inspect_time >= start,
                Inspection.inspect_time < end,
            )
        ) or 0
        avg_score = db.scalar(
            select(func.avg(Inspection.score)).where(
                Inspection.restroom_id == restroom.id,
                Inspection.inspect_time >= start,
                Inspection.inspect_time < end,
            )
        )
        issue_reported = db.scalar(
            select(func.count())
            .select_from(Issue)
            .where(
                Issue.restroom_id == restroom.id,
                Issue.report_time >= start,
                Issue.report_time < end,
            )
        ) or 0
        issue_closed = db.scalar(
            select(func.count())
            .select_from(Issue)
            .where(
                Issue.restroom_id == restroom.id,
                Issue.closed_at.is_not(None),
                Issue.closed_at >= start,
                Issue.closed_at < end,
            )
        ) or 0
        issue_overdue = db.scalar(
            select(func.count())
            .select_from(Issue)
            .where(
                Issue.restroom_id == restroom.id,
                Issue.deadline.is_not(None),
                Issue.deadline < now,
                Issue.status.in_(OPEN_ISSUE_STATUSES),
            )
        ) or 0

        db.add(
            MonthlyAssessment(
                restroom_id=restroom.id,
                year_month=year_month,
                open_days=open_days,
                expected_inspections=expected,
                actual_inspections=actual,
                missed_inspections=max(0, expected - actual),
                avg_score=round(float(avg_score), 1) if avg_score is not None else None,
                issue_reported=issue_reported,
                issue_closed=issue_closed,
                issue_overdue=issue_overdue,
                generated_at=now,
            )
        )
        generated += 1

    db.commit()
    return AssessmentGenerateResult(
        year_month=year_month,
        generated=generated,
        skipped=skipped,
        message=(
            f"已生成 {generated} 条 {year_month} 月度考核"
            + (f"，{skipped} 条已存在未重复生成" if skipped else "")
        ),
    )


def list_assessments(db: Session, year_month: str | None = None) -> list[MonthlyAssessmentOut]:
    stmt = select(MonthlyAssessment, Restroom).join(
        Restroom, Restroom.id == MonthlyAssessment.restroom_id
    )
    if year_month:
        stmt = stmt.where(MonthlyAssessment.year_month == year_month)
    stmt = stmt.order_by(MonthlyAssessment.year_month.desc(), Restroom.code)
    results: list[MonthlyAssessmentOut] = []
    for assessment, restroom in db.execute(stmt):
        out = MonthlyAssessmentOut.model_validate(assessment)
        out.restroom_code = restroom.code
        out.restroom_name = restroom.name
        out.district = restroom.district
        results.append(out)
    return results


def available_assessment_months(db: Session) -> list[str]:
    stmt = select(MonthlyAssessment.year_month).distinct().order_by(
        MonthlyAssessment.year_month.desc()
    )
    return list(db.scalars(stmt))
