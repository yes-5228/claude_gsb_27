"""公厕状态联动模型：状态变更留痕、停用区间、整改期限顺延与月度考核快照。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RestroomStatusEvent(Base):
    """公厕开放状态变更留痕，停用与恢复都会记录。"""

    __tablename__ = "restroom_status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    from_status: Mapped[str] = mapped_column(String(20), default="", comment="原状态")
    to_status: Mapped[str] = mapped_column(String(20), comment="新状态")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="变更原因")
    operator: Mapped[str] = mapped_column(String(60), default="", comment="操作人")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="变更时间"
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="status_events")  # noqa: F821


class SuspensionPeriod(Base):
    """一段停用区间：转入维修/暂停时开启，恢复开放时关闭。

    顺延决策在停用开启时按当时生效的规则快照到 extend_days，
    之后规则调整不影响本次区间（只影响此后的判定）。
    """

    __tablename__ = "suspension_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True, comment="停用开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True, comment="恢复开放时间，未恢复为空"
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="停用原因")
    operator: Mapped[str] = mapped_column(String(60), default="", comment="操作人")
    # 顺延决策快照：None=不顺延，0=按实际停用时长顺延，>0=固定顺延天数
    extend_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="顺延方式快照（空=不顺延，0=按停用时长，>0=固定天数）"
    )
    extension_settled: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="顺延是否已在恢复时结算"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    restroom: Mapped["Restroom"] = relationship(back_populates="suspension_periods")  # noqa: F821


class DeadlineExtensionRule(Base):
    """整改期限顺延规则，带生效时间，只影响生效之后发生的停用判定。"""

    __tablename__ = "deadline_extension_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime, index=True, comment="规则生效时间，只影响此后的判定"
    )
    extend_days: Mapped[int] = mapped_column(
        Integer, default=0, comment="顺延天数，0 表示按实际停用时长顺延"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="规则说明")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class IssueDeadlineExtension(Base):
    """问题期限顺延记录，(问题, 停用区间) 唯一，保证同一区间不重复顺延。"""

    __tablename__ = "issue_deadline_extensions"
    __table_args__ = (
        UniqueConstraint("issue_id", "suspension_period_id", name="uq_issue_period_extension"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True, comment="所属问题"
    )
    suspension_period_id: Mapped[int] = mapped_column(
        ForeignKey("suspension_periods.id", ondelete="CASCADE"), index=True, comment="停用区间"
    )
    old_deadline: Mapped[datetime] = mapped_column(DateTime, comment="顺延前期限")
    new_deadline: Mapped[datetime] = mapped_column(DateTime, comment="顺延后期限")
    days: Mapped[float] = mapped_column(Float, default=0.0, comment="顺延天数")
    reason: Mapped[str] = mapped_column(String(200), default="", comment="顺延原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MonthlyAssessment(Base):
    """月度考核快照：生成后冻结，后续状态变化与顺延不回溯影响。"""

    __tablename__ = "monthly_assessments"
    __table_args__ = (
        UniqueConstraint("restroom_id", "year_month", name="uq_restroom_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    year_month: Mapped[str] = mapped_column(String(7), index=True, comment="考核月份，如 2026-09")
    open_days: Mapped[int] = mapped_column(Integer, default=0, comment="当月开放天数")
    expected_inspections: Mapped[int] = mapped_column(Integer, default=0, comment="应巡查次数")
    actual_inspections: Mapped[int] = mapped_column(Integer, default=0, comment="实际巡查次数")
    missed_inspections: Mapped[int] = mapped_column(Integer, default=0, comment="漏巡次数")
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="当月巡查均分")
    issue_reported: Mapped[int] = mapped_column(Integer, default=0, comment="当月上报问题数")
    issue_closed: Mapped[int] = mapped_column(Integer, default=0, comment="当月闭环问题数")
    issue_overdue: Mapped[int] = mapped_column(Integer, default=0, comment="生成时点超期未闭环数")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="考核生成时间"
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="assessments")  # noqa: F821
