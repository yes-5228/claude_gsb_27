"""月度考核相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.restroom import RestroomBrief


class MonthlyAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom: RestroomBrief | None = None
    month: str
    expected_count: int
    actual_count: int
    missed_count: int
    avg_score: float | None = None
    issue_new: int
    issue_closed: int
    score: float
    result: str
    operator: str
    generated_at: datetime


class AssessmentGenerateRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="考核月份，如 2026-09")
    operator: str = Field(default="系统", max_length=60, description="生成人")


class AssessmentGenerateResult(BaseModel):
    month: str
    created: int = Field(description="本次新生成的考核数")
    skipped: int = Field(description="已存在、未重复生成的考核数")
