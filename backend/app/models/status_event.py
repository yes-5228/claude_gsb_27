"""公厕开放状态变更流水模型。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RestroomStatusEvent(Base):
    """一次开放状态变更（停用/恢复/调整），全程留痕可追溯。"""

    __tablename__ = "restroom_status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    from_status: Mapped[str] = mapped_column(String(20), comment="原状态")
    to_status: Mapped[str] = mapped_column(String(20), comment="新状态")
    reason: Mapped[str] = mapped_column(Text, default="", comment="变更原因")
    operator: Mapped[str] = mapped_column(String(60), default="", comment="操作人")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="变更时间"
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="status_events")  # noqa: F821
