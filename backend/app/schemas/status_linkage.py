"""公厕状态联动相关数据结构：状态变更、停用区间、顺延规则与月度考核。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import RestroomStatus


class RestroomStatusChange(BaseModel):
    """一次公厕开放状态变更请求。"""

    to_status: RestroomStatus = Field(description="目标状态")
    reason: str | None = Field(default=None, max_length=500, description="变更原因")
    operator: str = Field(default="", max_length=60, description="操作人")


class StatusEventOut(BaseModel):
    """状态变更留痕。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    from_status: str
    to_status: str
    reason: str | None = None
    operator: str
    created_at: datetime


class SuspensionPeriodOut(BaseModel):
    """一段停用区间。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    started_at: datetime
    ended_at: datetime | None = None
    reason: str | None = None
    operator: str
    extend_days: int | None = None
    extension_settled: bool = False


class StatusChangeResult(BaseModel):
    """状态变更的联动结果。"""

    restroom_id: int
    from_status: str
    to_status: str
    event_id: int
    suspension_period_id: int | None = None
    extended_issue_count: int = Field(default=0, description="本次恢复结算顺延的问题数")
    message: str = ""


class DeadlineExtensionRuleCreate(BaseModel):
    """新建顺延规则。"""

    effective_from: datetime = Field(description="规则生效时间，只影响此后的判定")
    extend_days: int = Field(default=0, ge=0, description="顺延天数，0 表示按实际停用时长顺延")
    note: str | None = Field(default=None, max_length=500, description="规则说明")
    active: bool = Field(default=True, description="是否启用")


class DeadlineExtensionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    effective_from: datetime
    extend_days: int
    note: str | None = None
    active: bool
    created_at: datetime


class MonthlyAssessmentOut(BaseModel):
    """月度考核快照。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom_code: str = ""
    restroom_name: str = ""
    district: str = ""
    year_month: str
    open_days: int
    expected_inspections: int
    actual_inspections: int
    missed_inspections: int
    avg_score: float | None = None
    issue_reported: int
    issue_closed: int
    issue_overdue: int
    generated_at: datetime


class AssessmentGenerateResult(BaseModel):
    """月度考核生成结果。"""

    year_month: str
    generated: int = Field(description="本次新生成的考核条数")
    skipped: int = Field(default=0, description="已存在而跳过的条数")
    message: str = ""
