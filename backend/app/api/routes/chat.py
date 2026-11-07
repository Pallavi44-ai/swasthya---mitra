from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.security import rate_limiter
from app.models import ChatMessage, ChatSession
from app.schemas.chat import ChatIn, ChatOut, MessageOut, SessionOut
from app.services import chat_service
from app.services.consent import has_consent

router = APIRouter(prefix="/chat", tags=["companion"])


def _own_session(db, user, sid: str) -> ChatSession:
    s = db.get(ChatSession, sid)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return s


@router.post("", response_model=ChatOut)
def send(body: ChatIn, user: CurrentUser, db: DB):
    rate_limiter.check(f"chat:{user.id}", 30, 300)
    session = _own_session(db, user, body.session_id) if body.session_id else None
    out, session = chat_service.handle_message(db, user, body, session)
    if has_consent(db, user.id, "store_chat_history"):
        chat_service.persist_turn(db, user, session, body.message.strip(), out)
    return out


@router.get("/sessions", response_model=list[SessionOut])
def sessions(user: CurrentUser, db: DB):
    rows = db.scalars(select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.created_at.desc()).limit(50))
    return [SessionOut(id=s.id, title=s.title, created_at=s.created_at) for s in rows]


@router.get("/sessions/{sid}/messages", response_model=list[MessageOut])
def messages(sid: str, user: CurrentUser, db: DB):
    s = _own_session(db, user, sid)
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == s.id).order_by(ChatMessage.created_at, ChatMessage.id))
    return [MessageOut(id=m.id, role=m.role, content=m.content, language=m.language, safety_level=m.safety_level, sources=m.sources, created_at=m.created_at) for m in rows]


@router.delete("/sessions/{sid}", status_code=204)
def delete_session(sid: str, user: CurrentUser, db: DB):
    db.delete(_own_session(db, user, sid))
    db.commit()
