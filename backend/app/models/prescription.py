from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import EncryptedJSON, EncryptedText
from app.db.session import Base
from app.db.types import UTCDateTime, new_id, utcnow

PRESCRIPTION_STATUSES = ("extracted", "confirmed", "failed", "discarded")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(15), default="extracted")
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # encrypted file on disk
    image_mime: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_engine: Mapped[str] = mapped_column(String(40), default="none")
    ocr_text: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    prescribed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    items: Mapped[list["PrescriptionItem"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="PrescriptionItem.position"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prescription_id: Mapped[str] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    medicine_name: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    strength: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    form: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dosage_instruction: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # verbatim, e.g. "1-0-1 after food"
    frequency_text: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    duration_text: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 – see services.prescription
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    flags: Mapped[list | None] = mapped_column(EncryptedJSON, nullable=True)  # list[str] reasons
    edited_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
