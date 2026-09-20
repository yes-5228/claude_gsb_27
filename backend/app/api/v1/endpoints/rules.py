"""整改期限顺延规则接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rule import DeadlineRuleCreate, DeadlineRuleOut, DeadlineRuleUpdate
from app.services import rule_service

router = APIRouter(prefix="/deadline-rules", tags=["顺延规则"])


@router.get("", response_model=list[DeadlineRuleOut], summary="顺延规则列表")
def list_rules(db: Annotated[Session, Depends(get_db)]) -> list[DeadlineRuleOut]:
    return [DeadlineRuleOut.model_validate(rule) for rule in rule_service.list_rules(db)]


@router.post("", response_model=DeadlineRuleOut, status_code=201, summary="新增顺延规则")
def create_rule(
    payload: DeadlineRuleCreate, db: Annotated[Session, Depends(get_db)]
) -> DeadlineRuleOut:
    return DeadlineRuleOut.model_validate(rule_service.create_rule(db, payload))


@router.patch("/{rule_id}", response_model=DeadlineRuleOut, summary="更新顺延规则")
def update_rule(
    rule_id: int, payload: DeadlineRuleUpdate, db: Annotated[Session, Depends(get_db)]
) -> DeadlineRuleOut:
    return DeadlineRuleOut.model_validate(rule_service.update_rule(db, rule_id, payload))
