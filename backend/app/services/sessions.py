"""Server-side session records: device list, revocation, idle + absolute timeouts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(db: Session, user: User, request: Request | None, method: str) -> UserSession:
    ua = (request.headers.get("user-agent", "") if request else "")[:200] or None
    s = UserSession(user_id=user.id, user_agent=ua, method=method)
    db.add(s)
    db.commit()
    return s


def validate(db: Session, sid: str | None, user_id: str) -> UserSession:
    s = db.get(UserSession, sid) if sid else None
    now = _now()
    if not s or s.user_id != user_id or s.revoked_at:
        raise HTTPException(401, "Session no longer valid")
    if now - s.last_seen_at > timedelta(minutes=get_settings().session_idle_minutes):
        s.revoked_at = now
        db.commit()
        raise HTTPException(401, "Your session timed out because you were away. Please log in again.")
    if now - s.last_seen_at > timedelta(seconds=60):  # throttle writes
        s.last_seen_at = now
        db.commit()
    return s


def revoke(db: Session, sid: str, user_id: str) -> bool:
    s = db.get(UserSession, sid)
    if not s or s.user_id != user_id or s.revoked_at:
        return False
    s.revoked_at = _now()
    db.commit()
    return True


def revoke_all(db: Session, user_id: str, except_sid: str | None = None) -> None:
    q = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_sid:
        q = q.where(UserSession.id != except_sid)
    db.execute(q.values(revoked_at=_now()))
    db.commit()


def active(db: Session, user_id: str) -> list[UserSession]:
    return list(db.scalars(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None)).order_by(UserSession.last_seen_at.desc())))
