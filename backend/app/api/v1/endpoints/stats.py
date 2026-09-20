"""统计看板接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.stats import DashboardStats, OverviewStats
from app.schemas.status_linkage import (
    AssessmentGenerateResult,
    MonthlyAssessmentOut,
)
from app.services import stats_service, status_linkage_service

router = APIRouter(prefix="/stats", tags=["统计看板"])


class AssessmentGenerateRequest(BaseModel):
    year_month: str = Field(description="考核月份，格式 YYYY-MM，如 2026-09", pattern=r"^\d{4}-\d{2}$")


@router.get("/overview", response_model=OverviewStats, summary="核心指标")
def get_overview(db: Annotated[Session, Depends(get_db)]) -> OverviewStats:
    return stats_service.overview(db)


@router.get("/dashboard", response_model=DashboardStats, summary="看板聚合数据")
def get_dashboard(
    db: Annotated[Session, Depends(get_db)],
    trend_days: Annotated[int, Query(ge=3, le=60, description="趋势天数")] = 14,
) -> DashboardStats:
    return stats_service.dashboard(db, trend_days=trend_days)


@router.post(
    "/assessments/generate",
    response_model=AssessmentGenerateResult,
    summary="生成月度考核快照（已生成的不重复）",
)
def generate_assessments(
    payload: AssessmentGenerateRequest, db: Annotated[Session, Depends(get_db)]
) -> AssessmentGenerateResult:
    return status_linkage_service.generate_assessments(db, payload.year_month)


@router.get(
    "/assessments/months",
    response_model=list[str],
    summary="已生成考核的月份列表",
)
def assessment_months(db: Annotated[Session, Depends(get_db)]) -> list[str]:
    return status_linkage_service.available_assessment_months(db)


@router.get("/assessments", response_model=list[MonthlyAssessmentOut], summary="月度考核列表")
def list_assessments(
    db: Annotated[Session, Depends(get_db)],
    year_month: Annotated[str | None, Query(description="按月份过滤，格式 YYYY-MM")] = None,
) -> list[MonthlyAssessmentOut]:
    return status_linkage_service.list_assessments(db, year_month)
