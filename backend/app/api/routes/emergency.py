"""Emergency Assistance (report module 6): 108 / helplines, emergency contacts, location hand-off."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DB, CurrentUser
from app.models import EmergencyEvent
from app.services import safety
from app.services.consent import has_consent

router = APIRouter(prefix="/emergency", tags=["emergency"])


class LocationIn(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


@router.get("")
def info(user: CurrentUser, db: DB):
    from app.api.routes.profile import list_contacts

    return {
        "numbers": [*safety.EMERGENCY_NUMBERS, safety.SELF_HARM_NUMBERS[0]],
        "contacts": [c.model_dump() for c in list_contacts(user, db)],
        "location_sharing_allowed": has_consent(db, user.id, "emergency_sharing"),
    }


@router.post("/open")
def opened(user: CurrentUser, db: DB):
    """Log that the emergency screen was opened (no content stored)."""
    db.add(EmergencyEvent(user_id=user.id, trigger="manual", severity="emergency", flags=[]))
    db.commit()
    return {"ok": True}


@router.post("/share-message")
def share_message(body: LocationIn, user: CurrentUser, db: DB):
    """Build a ready-to-send alert text for the user's emergency contacts. Nothing is sent from the
    server (no SMS provider is configured); the app opens the user's own SMS/WhatsApp with this text.
    Location is only included when the user has granted 'emergency_sharing' consent."""
    from app.api.routes.profile import list_contacts

    allowed = has_consent(db, user.id, "emergency_sharing")
    text = f"EMERGENCY: {user.full_name} needs urgent help. Please call them now."
    if allowed and body.latitude is not None and body.longitude is not None:
        text += f" Location: https://maps.google.com/?q={body.latitude:.5f},{body.longitude:.5f}"
    contacts = []
    for c in list_contacts(user, db):
        phone = c.phone.lstrip("+")
        contacts.append({
            **c.model_dump(), "sms_href": f"sms:{c.phone}?body={quote(text)}",
            "whatsapp_href": f"https://wa.me/{phone}?text={quote(text)}", "tel_href": f"tel:{c.phone}",
        })
    return {"message": text, "location_included": allowed and body.latitude is not None, "contacts": contacts}
