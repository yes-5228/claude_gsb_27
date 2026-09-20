"""公厕开放状态联动：状态变更留痕、巡查任务联动、整改期限顺延、应巡/漏检判定。"""

from datetime import date, datetime, time, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import OPEN_RESTROOM_STATUS
from app.core.exceptions import DomainError
from app.models import Inspection, Restroom, RestroomStatusEvent
from app.schemas.restroom import RestroomStatusChange
from app.services import restroom_service, rule_service, task_service


def list_events(db: Session, restroom_id: int) -> list[RestroomStatusEvent]:
    """按时间正序返回一座公厕的全部状态变更流水。"""
    return list(
        db.scalars(
            select(RestroomStatusEvent)
            .where(RestroomStatusEvent.restroom_id == restroom_id)
            .order_by(RestroomStatusEvent.created_at, RestroomStatusEvent.id)
        )
    )


def status_at(
    moment: datetime, events: list[RestroomStatusEvent], current_status: str
) -> str:
    """根据变更流水推算某一时刻的开放状态；无流水时以当前状态为准。"""
    if not events:
        return current_status
    status = events[0].from_status
    for event in events:
        if event.created_at <= moment:
            status = event.to_status
        else:
            break
    return status


def open_dates(
    events: list[RestroomStatusEvent],
    current_status: str,
    created_at: datetime,
    start: date,
    end: date,
) -> set[date]:
    """计算 [start, end] 内公厕处于开放状态（含部分时段开放）的日期集合。

    建档日之前的日期不算应巡；一天内只要开放过就算应巡，停用当日的空白不算漏检。
    """
    days: set[date] = set()
    if end < start:
        return days
    first_day = max(start, created_at.date())
    day = first_day
    while day <= end:
        day_start = datetime.combine(day, time.min)
        if status_at(day_start, events, current_status) == OPEN_RESTROOM_STATUS:
            days.add(day)
        else:
            day_end = datetime.combine(day, time.max)
            for event in events:
                if day_start <= event.created_at <= day_end and event.to_status == OPEN_RESTROOM_STATUS:
                    days.add(day)
                    break
        day += timedelta(days=1)
    return days


def change_status(
    db: Session, restroom_id: int, payload: RestroomStatusChange
) -> tuple[Restroom, RestroomStatusEvent, dict]:
    """变更开放状态，并联动巡查任务与未闭环问题期限。

    - 开放 -> 停用：取消当日及以后的待执行任务；按生效中的顺延规则顺延未闭环问题期限；
    - 停用 -> 开放：恢复当日及以后被取消的任务（原行恢复，不重复生成）；
    - 停用 -> 停用：只留痕，不重复取消、不重复顺延。
    """
    restroom = restroom_service.get_restroom(db, restroom_id)
    to_status = payload.to_status.value
    from_status = restroom.status
    if to_status == from_status:
        raise DomainError(f"公厕已处于「{to_status}」状态，无需变更")

    now = datetime.now()
    event = RestroomStatusEvent(
        restroom_id=restroom.id,
        from_status=from_status,
        to_status=to_status,
        reason=payload.reason.strip(),
        operator=payload.operator.strip(),
        created_at=now,
    )
    db.add(event)
    restroom.status = to_status

    summary = {"cancelled_tasks": 0, "revived_tasks": 0, "extended_issues": 0, "applied_rule": None}
    was_open = from_status == OPEN_RESTROOM_STATUS
    will_open = to_status == OPEN_RESTROOM_STATUS
    if was_open and not will_open:
        reason = f"公厕转入「{to_status}」：{event.reason}"
        summary["cancelled_tasks"] = task_service.cancel_pending_tasks(
            db, restroom.id, from_date=now.date(), reason=reason, at=now
        )
        extended, rule_name = rule_service.extend_open_issues(
            db, restroom, to_status, now=now, operator=event.operator
        )
        summary["extended_issues"] = extended
        summary["applied_rule"] = rule_name
    elif will_open and not was_open:
        summary["revived_tasks"] = task_service.restore_pending_tasks(
            db, restroom.id, from_date=now.date(), at=now
        )

    db.commit()
    db.refresh(restroom)
    db.refresh(event)
    return restroom, event, summary


def _events_by_restroom(
    db: Session, restroom_ids: Iterable[int]
) -> dict[int, list[RestroomStatusEvent]]:
    ids = list(restroom_ids)
    if not ids:
        return {}
    rows = db.scalars(
        select(RestroomStatusEvent)
        .where(RestroomStatusEvent.restroom_id.in_(ids))
        .order_by(RestroomStatusEvent.created_at, RestroomStatusEvent.id)
    ).all()
    grouped: dict[int, list[RestroomStatusEvent]] = {rid: [] for rid in ids}
    for row in rows:
        grouped.setdefault(row.restroom_id, []).append(row)
    return grouped


def open_days_for(db: Session, restroom: Restroom, start: date, end: date) -> set[date]:
    """单座公厕在 [start, end] 内的应巡日期集合。"""
    events = list_events(db, restroom.id)
    return open_dates(events, restroom.status, restroom.created_at, start, end)


def missed_by_day(
    db: Session, start: date, end: date, restroom_id: int | None = None
) -> dict[date, int]:
    """按日统计漏检：应巡日（已过去）没有任何巡查记录计 1 次漏检。

    停用期间的空白不算漏检；当天尚未结束，不计入漏检。
    """
    today = datetime.now().date()
    end = min(end, today - timedelta(days=1))
    counts: dict[date, int] = {}
    if end < start:
        return counts

    stmt = select(Restroom)
    if restroom_id is not None:
        stmt = stmt.where(Restroom.id == restroom_id)
    restrooms = list(db.scalars(stmt))
    if not restrooms:
        return counts

    events_map = _events_by_restroom(db, [room.id for room in restrooms])
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)
    inspected: set[tuple[int, date]] = set()
    rows = db.execute(
        select(Inspection.restroom_id, Inspection.inspect_time).where(
            Inspection.inspect_time >= start_dt, Inspection.inspect_time <= end_dt
        )
    ).all()
    for rid, inspect_time in rows:
        inspected.add((rid, inspect_time.date()))

    day = start
    while day <= end:
        counts[day] = 0
        day += timedelta(days=1)
    for room in restrooms:
        open_days = open_dates(
            events_map.get(room.id, []), room.status, room.created_at, start, end
        )
        for day in open_days:
            if (room.id, day) not in inspected:
                counts[day] = counts.get(day, 0) + 1
    return counts


def missed_count(db: Session, start: date, end: date, restroom_id: int | None = None) -> int:
    """[start, end] 内的漏检总次数。"""
    return sum(missed_by_day(db, start, end, restroom_id=restroom_id).values())


__all__ = [
    "list_events",
    "status_at",
    "open_dates",
    "change_status",
    "open_days_for",
    "missed_by_day",
    "missed_count",
]
