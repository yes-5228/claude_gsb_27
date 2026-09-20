"""整改期限顺延规则接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.status_linkage import DeadlineExtensionRuleCreate, DeadlineExtensionRuleOut
from app.services import status_linkage_service

router = APIRouter(prefix="/rules/deadline-extensions", tags=["顺延规则"])


@router.get("", response_model=list[DeadlineExtensionRuleOut], summary="顺延规则列表")
def list_rules(db: Annotated[Session, Depends(get_db)]) -> list[DeadlineExtensionRuleOut]:
    rules = status_linkage_service.list_rules(db)
    return [DeadlineExtensionRuleOut.model_validate(rule) for rule in rules]


@router.post("", response_model=DeadlineExtensionRuleOut, status_code=201, summary="新建顺延规则")
def create_rule(
    payload: DeadlineExtensionRuleCreate, db: Annotated[Session, Depends(get_db)]
) -> DeadlineExtensionRuleOut:
    rule = status_linkage_service.create_rule(db, payload)
    return DeadlineExtensionRuleOut.model_validate(rule)
