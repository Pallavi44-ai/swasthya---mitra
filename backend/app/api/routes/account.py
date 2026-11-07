"""Privacy controls: consent management, data export and deletion (report §4.10)."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.security import COOKIE_NAME, verify_password
from app.models import (
    AuditLog, ChatMessage, ConsentRecord, DoseLog, EmergencyContact, EmergencyEvent, HealthProfile,
    HealthRecord, Prescription, Reminder,
)
from app.schemas.auth import ConsentUpdate, DeleteAccountIn, UserOut, UserUpdate
from app.services.consent import current_consents, set_consents

router = APIRouter(tags=["account"])
log = logging.getLogger(__name__)


@router.patch("/account", response_model=UserOut)
def update_account(body: UserUpdate, user: CurrentUser, db: DB):
    if body.timezone:
        from zoneinfo import ZoneInfo

        try:
            ZoneInfo(body.timezone)
        except Exception:
            raise HTTPException(422, "Unknown timezone")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    db.commit()
    return user


@router.get("/consents")
def get_consents(user: CurrentUser, db: DB):
    return {"consents": current_consents(db, user.id)}


@router.put("/consents")
def update_consents(body: ConsentUpdate, user: CurrentUser, db: DB):
    return {"consents": set_consents(db, user.id, body.consents)}


def _iso(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


@router.get("/account/export")
def export_data(user: CurrentUser, db: DB):
    """Everything we hold about the user, as JSON (right of access / portability)."""
    uid = user.id
    prof = db.get(HealthProfile, uid)
    prescriptions = db.scalars(select(Prescription).where(Prescription.user_id == uid)).all()
    data = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "user": UserOut.model_validate(user).model_dump(mode="json"),
        "consents": [
            {"purpose": c.purpose, "granted": c.granted, "at": _iso(c.created_at)}
            for c in db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == uid))
        ],
        "profile": None if not prof else {
            "date_of_birth": _iso(prof.date_of_birth), "sex": prof.sex, "blood_group": prof.blood_group,
            "height_cm": prof.height_cm, "weight_kg": prof.weight_kg, "allergies": prof.allergies,
            "conditions": prof.conditions, "notes": prof.notes,
        },
        "emergency_contacts": [
            {"name": c.name, "phone": c.phone, "relationship": c.relationship_}
            for c in db.scalars(select(EmergencyContact).where(EmergencyContact.user_id == uid))
        ],
        "records": [
            {"type": r.record_type, "title": r.title, "date": _iso(r.record_date), "details": r.details}
            for r in db.scalars(select(HealthRecord).where(HealthRecord.user_id == uid))
        ],
        "prescriptions": [
            {
                "status": p.status, "created_at": _iso(p.created_at),
                "items": [
                    {"medicine": i.medicine_name, "strength": i.strength, "dosage": i.dosage_instruction,
                     "duration": i.duration_text, "confirmed": i.user_confirmed}
                    for i in p.items
                ],
            }
            for p in prescriptions
        ],
        "reminders": [
            {"item_id": r.prescription_item_id, "times": r.times, "start": _iso(r.start_date), "end": _iso(r.end_date)}
            for r in db.scalars(select(Reminder).where(Reminder.user_id == uid))
        ],
        "dose_log": [
            {"scheduled_at": _iso(d.scheduled_at), "status": d.status}
            for d in db.scalars(select(DoseLog).where(DoseLog.user_id == uid))
        ],
        "chat_messages": [
            {"role": m.role, "content": m.content, "at": _iso(m.created_at)}
            for m in db.scalars(select(ChatMessage).where(ChatMessage.user_id == uid).order_by(ChatMessage.created_at))
        ],
        "emergency_events": [
            {"trigger": e.trigger, "flags": e.flags, "at": _iso(e.created_at)}
            for e in db.scalars(select(EmergencyEvent).where(EmergencyEvent.user_id == uid))
        ],
    }
    db.add(AuditLog(user_id=uid, action="data_export"))
    db.commit()
    return data


@router.delete("/account/chat-history", status_code=204)
def delete_chat_history(user: CurrentUser, db: DB):
    from sqlalchemy import delete

    from app.models import ChatSession

    db.execute(delete(ChatSession).where(ChatSession.user_id == user.id))  # messages cascade
    db.add(AuditLog(user_id=user.id, action="chat_history_deleted"))
    db.commit()


@router.post("/account/delete", status_code=204)
def delete_account(body: DeleteAccountIn, response: Response, user: CurrentUser, db: DB):
    """Permanent deletion of the account and all associated data, including stored images."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Password is incorrect")
    for p in db.scalars(select(Prescription).where(Prescription.user_id == user.id)):
        if p.image_path and os.path.exists(p.image_path):
            try:
                os.remove(p.image_path)
            except OSError:
                log.warning("Could not remove stored image for a deleted account")
    uid = user.id
    db.delete(user)  # DB-level ON DELETE CASCADE removes everything owned by the user
    db.add(AuditLog(user_id=None, action="account_deleted", detail=f"user={uid[:8]}"))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
