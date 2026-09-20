"""整改期限顺延规则业务逻辑：规则带生效时间，只影响生效后的判定。"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import OPEN_ISSUE_STATUSES
from app.core.exceptions import NotFoundError
from app.models import DeadlineRule, Issue, RectificationRecord, Restroom
from app.schemas.rule import DeadlineRuleCreate, DeadlineRuleUpdate


def list_rules(db: Session) -> list[DeadlineRule]:
    """按生效时间倒序返回全部顺延规则。"""
    return list(
        db.scalars(select(DeadlineRule).order_by(DeadlineRule.effective_from.desc(), DeadlineRule.id.desc()))
    )


def create_rule(db: Session, payload: DeadlineRuleCreate) -> DeadlineRule:
    rule = DeadlineRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule_id: int, payload: DeadlineRuleUpdate) -> DeadlineRule:
    rule = db.get(DeadlineRule, rule_id)
    if rule is None:
        raise NotFoundError(f"顺延规则 {rule_id} 不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


def resolve_rule(db: Session, to_status: str, moment: datetime) -> DeadlineRule | None:
    """找到判定时刻生效中的顺延规则：启用、覆盖目标状态、生效时间不晚于判定时刻，取最新生效的一条。"""
    rules = list(
        db.scalars(
            select(DeadlineRule)
            .where(DeadlineRule.enabled.is_(True), DeadlineRule.effective_from <= moment)
            .order_by(DeadlineRule.effective_from.desc(), DeadlineRule.id.desc())
        )
    )
    for rule in rules:
        if to_status in (rule.trigger_statuses or []):
            return rule
    return None


def extend_open_issues(
    db: Session, restroom: Restroom, to_status: str, *, now: datetime, operator: str
) -> tuple[int, str | None]:
    """公厕转入停用时，按生效中的规则顺延未闭环问题的整改期限并说明原因。

    返回 (顺延的问题数, 命中的规则名称)；无命中规则或顺延天数为 0 时不做变更。
    """
    rule = resolve_rule(db, to_status, now)
    if rule is None:
        return 0, None

    issues = list(
        db.scalars(
            select(Issue).where(
                Issue.restroom_id == restroom.id,
                Issue.status.in_(OPEN_ISSUE_STATUSES),
                Issue.deadline.is_not(None),
            )
        )
    )
    if rule.extend_days <= 0 or not issues:
        return 0, rule.name

    delta = timedelta(days=rule.extend_days)
    for issue in issues:
        old_deadline = issue.deadline
        issue.deadline = old_deadline + delta
        issue.records.append(
            RectificationRecord(
                action="期限顺延",
                from_status=issue.status,
                to_status=issue.status,
                operator=operator,
                remark=(
                    f"公厕转入「{to_status}」，按顺延规则「{rule.name}」顺延 {rule.extend_days} 天："
                    f"{old_deadline:%Y-%m-%d %H:%M} → {issue.deadline:%Y-%m-%d %H:%M}"
                ),
                created_at=now,
            )
        )
    return len(issues), rule.name
