from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    language: Literal["en", "hi", "kn", "te"] | None = None  # UI/voice language hint
    history: list[HistoryTurn] = Field(default_factory=list, max_length=12)  # used only when history isn't stored


class Source(BaseModel):
    n: int
    title: str
    section: str
    source_name: str
    source_url: str | None = None
    review_status: str


class Action(BaseModel):
    label: str
    href: str


class SafetyOut(BaseModel):
    level: Literal["none", "urgent", "emergency"]
    flags: list[str] = []
    labels: list[str] = []
    banner: str | None = None
    numbers: list[dict] = []
    contacts: list[dict] = []


class ChatOut(BaseModel):
    session_id: str | None
    reply: str
    language: str
    mode: Literal["emergency", "llm_rag", "general_chat", "retrieval_only", "navigation", "unavailable", "companion"]
    unavailable_reason: Literal["no_consent", "not_configured", "error"] | None = None
    safety: SafetyOut
    sources: list[Source] = []
    actions: list[Action] = []
    disclaimer: str
    stored: bool
    guard_removed: list[str] = []
    topic: Literal["health", "general", "emotional", "activity"] | None = None  # lets the UI hide medical notes for chat/games


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    language: str
    safety_level: str | None
    sources: list | None
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
