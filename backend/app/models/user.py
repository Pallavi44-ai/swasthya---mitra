from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import UTCDateTime, new_id, utcnow

# Consent purposes (D2 in the DFD). Each is independently grantable/withdrawable.
CONSENT_PURPOSES = (
    "ai_processing",  # send questions / images to the external AI service
    "store_chat_history",  # keep conversations (encrypted)
    "health_data_personalisation",  # use profile, history & medicines to personalise answers
    "store_prescription_images",  # keep the uploaded prescription photo (encrypted)
    "emergency_sharing",  # allow location / contact hand-off in emergency screen
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(120))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")  # en | hi | kn | te
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)  # E.164, e.g. +919876543210
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_channel: Mapped[str] = mapped_column(String(5), default="email")  # email | sms – where login codes are sent
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    consents: Mapped[list["ConsentRecord"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class ConsentRecord(Base):
    """Append-only consent ledger – the latest row per purpose is the current state."""

    __tablename__ = "consent_records"
    __table_args__ = (Index("ix_consent_user_purpose", "user_id", "purpose", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(50))
    granted: Mapped[bool] = mapped_column(Boolean)
    policy_version: Mapped[str] = mapped_column(String(10), default="1.0")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
