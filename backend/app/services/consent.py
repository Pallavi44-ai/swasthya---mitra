"""Consent ledger helpers (DFD store D2). Server-side enforcement lives here, not in the UI."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CONSENT_PURPOSES, AuditLog, ConsentRecord

POLICY_VERSION = "1.0"


def current_consents(db: Session, user_id: str) -> dict[str, bool]:
    rows = db.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id).order_by(ConsentRecord.created_at, ConsentRecord.id)
    ).all()
    state = {p: False for p in CONSENT_PURPOSES}
    for r in rows:  # ordered oldest → newest, so the latest wins
        state[r.purpose] = r.granted
    return state


def has_consent(db: Session, user_id: str, purpose: str) -> bool:
    return current_consents(db, user_id).get(purpose, False)


def require_consent(db: Session, user_id: str, purpose: str, message: str) -> None:
    if not has_consent(db, user_id, purpose):
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "consent_required", "purpose": purpose, "message": message})


def set_consents(db: Session, user_id: str, changes: dict[str, bool]) -> dict[str, bool]:
    unknown = set(changes) - set(CONSENT_PURPOSES)
    if unknown:
        raise HTTPException(422, f"Unknown consent purpose(s): {sorted(unknown)}")
    state = current_consents(db, user_id)
    for purpose, granted in changes.items():
        if state.get(purpose) != granted:
            db.add(ConsentRecord(user_id=user_id, purpose=purpose, granted=granted, policy_version=POLICY_VERSION))
            db.add(AuditLog(user_id=user_id, action="consent_change", detail=f"{purpose}={granted}"))
    db.commit()
    return current_consents(db, user_id)
