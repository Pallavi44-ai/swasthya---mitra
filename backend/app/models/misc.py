from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import UTCDateTime, new_id, utcnow


class EmergencyEvent(Base):
    """Records that an escalation was shown. Deliberately stores flag ids only – not the user's text."""

    __tablename__ = "emergency_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(20))  # red_flag | llm_urgency | manual
    severity: Mapped[str] = mapped_column(String(12), default="emergency")
    flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class KnowledgeChunk(Base):
    """D4 – curated healthcare information used for RAG."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_kb_doc", "doc_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    doc_id: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    section: Mapped[str] = mapped_column(String(200), default="")
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="starter-unreviewed")
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class AuditLog(Base):
    """Security-relevant events (no health content): login, consent change, export, delete."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
