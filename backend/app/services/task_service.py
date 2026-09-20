"""巡查任务业务逻辑：按日生成、随开放状态取消/恢复，全程幂等。"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    OPEN_RESTROOM_STATUS,
    TASK_DISPLAY_MISSED,
    InspectionTaskStatus,
)
from app.models import InspectionTask, Restroom
from app.schemas.task import InspectionTaskOut


def ensure_tasks(db: Session, task_date: date) -> int:
    """为当日及以后日期生成任务：每座开放公厕每天一条，已存在则跳过（不重复）。"""
    restrooms = list(db.scalars(select(Restroom).where(Restroom.status == OPEN_RESTROOM_STATUS)))
    if not restrooms:
        return 0
    existing = set(
        db.scalars(
            select(InspectionTask.restroom_id).where(InspectionTask.task_date == task_date)
        ).all()
    )
    created = 0
    for restroom in restrooms:
        if restroom.id in existing:
            continue
        db.add(InspectionTask(restroom_id=restroom.id, task_date=task_date))
        created += 1
    if created:
        db.commit()
    return created


def cancel_pending_tasks(
    db: Session, restroom_id: int, *, from_date: date, reason: str, at: datetime
) -> int:
    """公厕停用时取消当日及以后的待执行任务；已取消/已完成的不受影响。"""
    tasks = list(
        db.scalars(
            select(InspectionTask).where(
                InspectionTask.restroom_id == restroom_id,
                InspectionTask.task_date >= from_date,
                InspectionTask.status == InspectionTaskStatus.PENDING.value,
            )
        )
    )
    for task in tasks:
        task.status = InspectionTaskStatus.CANCELLED.value
        task.cancel_reason = reason
        task.cancelled_at = at
    return len(tasks)


def restore_pending_tasks(db: Session, restroom_id: int, *, from_date: date, at: datetime) -> int:
    """公厕恢复开放时，把当日及以后被取消的任务原行恢复为待执行；缺失的当日任务补齐。"""
    tasks = list(
        db.scalars(
            select(InspectionTask).where(
                InspectionTask.restroom_id == restroom_id,
                InspectionTask.task_date >= from_date,
                InspectionTask.status == InspectionTaskStatus.CANCELLED.value,
            )
        )
    )
    for task in tasks:
        task.status = InspectionTaskStatus.PENDING.value
        task.cancel_reason = None
        task.cancelled_at = None
    restored = len(tasks)

    today_row = db.scalar(
        select(InspectionTask.id).where(
            InspectionTask.restroom_id == restroom_id,
            InspectionTask.task_date == from_date,
        )
    )
    if today_row is None:
        db.add(InspectionTask(restroom_id=restroom_id, task_date=from_date, generated_at=at))
        restored += 1
    return restored


def complete_task_for_inspection(
    db: Session, restroom_id: int, task_date: date, inspection_id: int
) -> None:
    """巡查记录提交后，把对应日期的待执行任务标记为已完成。"""
    task = db.scalar(
        select(InspectionTask).where(
            InspectionTask.restroom_id == restroom_id,
            InspectionTask.task_date == task_date,
            InspectionTask.status == InspectionTaskStatus.PENDING.value,
        )
    )
    if task is not None:
        task.status = InspectionTaskStatus.DONE.value
        task.inspection_id = inspection_id
        task.completed_at = datetime.now()
        db.commit()


def display_status(task: InspectionTask, today: date | None = None) -> str:
    """过期仍未执行的任务展示为「漏检」（不落库）。"""
    today = today or datetime.now().date()
    if task.status == InspectionTaskStatus.PENDING.value and task.task_date < today:
        return TASK_DISPLAY_MISSED
    return task.status


def to_out(task: InspectionTask) -> InspectionTaskOut:
    data = InspectionTaskOut.model_validate(task)
    data.display_status = display_status(task)
    return data


def list_tasks(
    db: Session,
    *,
    task_date: date,
    restroom_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[InspectionTask], int]:
    """按日期查询任务；查询当日/未来日期时先幂等补齐生成。"""
    if task_date >= datetime.now().date():
        ensure_tasks(db, task_date)
    stmt = select(InspectionTask).where(InspectionTask.task_date == task_date)
    if restroom_id:
        stmt = stmt.where(InspectionTask.restroom_id == restroom_id)
    if status:
        if status == TASK_DISPLAY_MISSED:
            stmt = stmt.where(
                InspectionTask.status == InspectionTaskStatus.PENDING.value,
                InspectionTask.task_date < datetime.now().date(),
            )
        else:
            stmt = stmt.where(InspectionTask.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(InspectionTask.restroom_id, InspectionTask.id)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total
