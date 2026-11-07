from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import UTCDateTime, new_id, utcnow


class Reminder(Base):
    """A medication schedule. prescription_item_id is NOT NULL: a reminder can only exist for a
    medicine line that the user has confirmed (enforced again in the service layer)."""

    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    prescription_item_id: Mapped[str] = mapped_column(ForeignKey("prescription_items.id", ondelete="CASCADE"))
    times: Mapped[list] = mapped_column(JSON)  # ["08:00", "21:00"] local time chosen by the user
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class DoseLog(Base):
    __tablename__ = "dose_logs"
    __table_args__ = (
        UniqueConstraint("reminder_id", "scheduled_at", name="uq_dose_slot"),
        Index("ix_dose_user_time", "user_id", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reminder_id: Mapped[str] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|taken|skipped|missed
    acted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
