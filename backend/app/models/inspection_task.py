"""巡查任务模型：每座公厕每个开放日生成一条，随开放状态联动。"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import InspectionTaskStatus
from app.core.database import Base


class InspectionTask(Base):
    """一座公厕一天的巡查任务；同一公厕同一天唯一，反复启停不会重复生成。"""

    __tablename__ = "inspection_tasks"
    __table_args__ = (
        UniqueConstraint("restroom_id", "task_date", name="uq_inspection_task_restroom_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    task_date: Mapped[date] = mapped_column(Date, index=True, comment="任务日期")
    status: Mapped[str] = mapped_column(
        String(20), default=InspectionTaskStatus.PENDING.value, index=True, comment="任务状态"
    )
    inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True, comment="关联巡查记录"
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="取消原因")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="生成时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="取消时间")

    restroom: Mapped["Restroom"] = relationship(back_populates="inspection_tasks")  # noqa: F821
