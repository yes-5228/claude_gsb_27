"""巡查任务相关数据结构。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.restroom import RestroomBrief


class InspectionTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom: RestroomBrief | None = None
    task_date: date
    status: str
    display_status: str = Field(default="", description="展示状态：过期未执行显示为漏检")
    inspection_id: int | None = None
    cancel_reason: str | None = None
    generated_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


class TaskGenerateResult(BaseModel):
    task_date: date
    created: int = Field(description="本次新生成的任务数")
    total: int = Field(description="当日任务总数")
