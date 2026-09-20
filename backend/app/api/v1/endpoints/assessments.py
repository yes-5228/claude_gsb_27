"""月度考核接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.assessment import (
    AssessmentGenerateRequest,
    AssessmentGenerateResult,
    MonthlyAssessmentOut,
)
from app.schemas.common import Page
from app.services import assessment_service

router = APIRouter(prefix="/assessments", tags=["月度考核"])


@router.get("", response_model=Page[MonthlyAssessmentOut], summary="月度考核列表")
def list_assessments(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    month: Annotated[str | None, Query(description="考核月份，如 2026-09")] = None,
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
) -> Page[MonthlyAssessmentOut]:
    rows, total = assessment_service.list_assessments(
        db, month=month, district=district, page=pagination.page, page_size=pagination.page_size
    )
    return Page[MonthlyAssessmentOut](
        items=[MonthlyAssessmentOut.model_validate(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("/generate", response_model=AssessmentGenerateResult, summary="生成月度考核")
def generate_assessments(
    payload: AssessmentGenerateRequest, db: Annotated[Session, Depends(get_db)]
) -> AssessmentGenerateResult:
    created, skipped = assessment_service.generate(db, payload.month, operator=payload.operator)
    return AssessmentGenerateResult(month=payload.month, created=created, skipped=skipped)
