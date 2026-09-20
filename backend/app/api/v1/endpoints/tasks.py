"""巡查任务接口。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import Page
from app.schemas.task import InspectionTaskOut, TaskGenerateResult
from app.services import task_service

router = APIRouter(prefix="/inspection-tasks", tags=["巡查任务"])


class TaskGenerateRequest(BaseModel):
    task_date: date = Field(description="任务日期，默认为当天")


@router.get("", response_model=Page[InspectionTaskOut], summary="巡查任务列表")
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    task_date: Annotated[date | None, Query(description="任务日期，默认当天")] = None,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
    status: Annotated[str | None, Query(description="任务状态（待执行/已完成/已取消/漏检）")] = None,
) -> Page[InspectionTaskOut]:
    target = task_date or date.today()
    rows, total = task_service.list_tasks(
        db,
        task_date=target,
        restroom_id=restroom_id,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page[InspectionTaskOut](
        items=[task_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("/generate", response_model=TaskGenerateResult, summary="生成指定日期的巡查任务")
def generate_tasks(
    payload: TaskGenerateRequest, db: Annotated[Session, Depends(get_db)]
) -> TaskGenerateResult:
    created = task_service.ensure_tasks(db, payload.task_date)
    _, total = task_service.list_tasks(db, task_date=payload.task_date, page=1, page_size=1)
    return TaskGenerateResult(task_date=payload.task_date, created=created, total=total)
