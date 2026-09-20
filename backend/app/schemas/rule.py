"""整改期限顺延规则相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import SUSPENDED_RESTROOM_STATUSES


class DeadlineRuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="规则名称")
    extend_days: int = Field(ge=0, le=365, description="每次停用顺延天数")
    trigger_statuses: list[str] = Field(
        default_factory=lambda: list(SUSPENDED_RESTROOM_STATUSES),
        description="触发顺延的停用状态",
    )
    effective_from: datetime = Field(description="生效时间，仅影响此后的判定")
    enabled: bool = Field(default=True, description="是否启用")
    remark: str | None = Field(default=None, max_length=500, description="规则说明")

    @field_validator("trigger_statuses")
    @classmethod
    def _check_statuses(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("至少选择一个触发状态")
        invalid = [item for item in value if item not in SUSPENDED_RESTROOM_STATUSES]
        if invalid:
            raise ValueError(f"无效的触发状态：{'、'.join(invalid)}")
        return value


class DeadlineRuleCreate(DeadlineRuleBase):
    pass


class DeadlineRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    extend_days: int | None = Field(default=None, ge=0, le=365)
    trigger_statuses: list[str] | None = None
    effective_from: datetime | None = None
    enabled: bool | None = None
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("trigger_statuses")
    @classmethod
    def _check_statuses(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("至少选择一个触发状态")
        invalid = [item for item in value if item not in SUSPENDED_RESTROOM_STATUSES]
        if invalid:
            raise ValueError(f"无效的触发状态：{'、'.join(invalid)}")
        return value


class DeadlineRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    extend_days: int
    trigger_statuses: list[str]
    effective_from: datetime
    enabled: bool
    remark: str | None = None
    created_at: datetime
