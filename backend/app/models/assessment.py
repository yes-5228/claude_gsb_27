"""月度考核快照模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MonthlyAssessment(Base):
    """一座公厕一个自然月的考核快照；发布后固化，不随后续状态变化改变。"""

    __tablename__ = "monthly_assessments"
    __table_args__ = (
        UniqueConstraint("restroom_id", "month", name="uq_assessment_restroom_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    month: Mapped[str] = mapped_column(String(7), index=True, comment="考核月份，如 2026-09")
    expected_count: Mapped[int] = mapped_column(Integer, default=0, comment="应巡天数")
    actual_count: Mapped[int] = mapped_column(Integer, default=0, comment="实际巡查次数")
    missed_count: Mapped[int] = mapped_column(Integer, default=0, comment="漏检天数")
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="巡查均分")
    issue_new: Mapped[int] = mapped_column(Integer, default=0, comment="当月新增问题")
    issue_closed: Mapped[int] = mapped_column(Integer, default=0, comment="当月闭环问题")
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="考核得分")
    result: Mapped[str] = mapped_column(String(20), default="", comment="考核结果")
    operator: Mapped[str] = mapped_column(String(60), default="", comment="生成人")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="生成时间"
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="assessments")  # noqa: F821
