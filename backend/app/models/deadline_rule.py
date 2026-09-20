"""整改期限顺延规则模型。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeadlineRule(Base):
    """公厕停用时未闭环问题的期限顺延规则；带生效时间，只影响生效后的判定。"""

    __tablename__ = "deadline_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), comment="规则名称")
    extend_days: Mapped[int] = mapped_column(Integer, default=0, comment="每次停用顺延天数")
    trigger_statuses: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="触发顺延的停用状态（维修中/暂停使用）"
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime, index=True, comment="生效时间，仅影响此后的判定"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="规则说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
