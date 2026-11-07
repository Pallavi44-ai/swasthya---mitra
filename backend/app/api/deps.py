from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import COOKIE_NAME, decode_access_token
from app.db.session import get_db
from app.models import User
from app.services import sessions

DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB,
    sm_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Authentication gate (DFD process 1.0). Nothing below it runs without a valid session."""
    token = sm_session
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_access_token(token)
    user = db.get(User, payload["sub"])
    if not user or not user.is_active or user.token_version != payload.get("ver"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session no longer valid")
    sess = sessions.validate(db, payload.get("sid"), user.id)  # revoked / idle-timeout check
    user._sid = sess.id  # type: ignore[attr-defined]
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
