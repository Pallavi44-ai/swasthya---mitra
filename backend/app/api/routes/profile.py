"""Health Profile & Records module (report module 5): profile, emergency contacts, records, timeline."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models import (
    EmergencyContact, EmergencyEvent, HealthProfile, HealthRecord, Prescription, PrescriptionItem,
)
from app.schemas.health import (
    ContactIn, ContactOut, ProfileIn, ProfileOut, RecordIn, RecordOut, TimelineEvent,
)

router = APIRouter(tags=["profile"])


def _age(dob: date | None) -> int | None:
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def _profile_out(p: HealthProfile | None) -> ProfileOut:
    if not p:
        return ProfileOut()
    out = ProfileOut.model_validate(p)
    out.age = _age(p.date_of_birth)
    out.allergies = p.allergies or []
    out.conditions = p.conditions or []
    return out


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: DB):
    return _profile_out(db.get(HealthProfile, user.id))


@router.put("/profile", response_model=ProfileOut)
def put_profile(body: ProfileIn, user: CurrentUser, db: DB):
    p = db.get(HealthProfile, user.id)
    if not p:
        p = HealthProfile(user_id=user.id)
        db.add(p)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return _profile_out(p)


# ---- Emergency contacts -------------------------------------------------------------------------
def _contact_out(c: EmergencyContact) -> ContactOut:
    return ContactOut(id=c.id, name=c.name, phone=c.phone, relationship=c.relationship_, is_primary=c.is_primary)


def _own_contact(db, user, cid: str) -> EmergencyContact:
    c = db.get(EmergencyContact, cid)
    if not c or c.user_id != user.id:  # same response for "missing" and "someone else's"
        raise HTTPException(404, "Contact not found")
    return c


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(user: CurrentUser, db: DB):
    rows = db.scalars(
        select(EmergencyContact).where(EmergencyContact.user_id == user.id)
        .order_by(EmergencyContact.is_primary.desc(), EmergencyContact.created_at)
    )
    return [_contact_out(c) for c in rows]


@router.post("/contacts", response_model=ContactOut, status_code=201)
def add_contact(body: ContactIn, user: CurrentUser, db: DB):
    existing = db.scalars(select(EmergencyContact).where(EmergencyContact.user_id == user.id)).all()
    if len(existing) >= 5:
        raise HTTPException(409, "You can save up to 5 emergency contacts")
    primary = body.is_primary or not existing
    if primary:
        for c in existing:
            c.is_primary = False
    c = EmergencyContact(user_id=user.id, name=body.name, phone=body.phone, relationship_=body.relationship, is_primary=primary)
    db.add(c)
    db.commit()
    return _contact_out(c)


@router.put("/contacts/{cid}", response_model=ContactOut)
def update_contact(cid: str, body: ContactIn, user: CurrentUser, db: DB):
    c = _own_contact(db, user, cid)
    if body.is_primary:
        for o in db.scalars(select(EmergencyContact).where(EmergencyContact.user_id == user.id)):
            o.is_primary = False
    c.name, c.phone, c.relationship_, c.is_primary = body.name, body.phone, body.relationship, body.is_primary
    db.commit()
    return _contact_out(c)


@router.delete("/contacts/{cid}", status_code=204)
def delete_contact(cid: str, user: CurrentUser, db: DB):
    db.delete(_own_contact(db, user, cid))
    db.commit()


# ---- Health records -----------------------------------------------------------------------------
def _own_record(db, user, rid: str) -> HealthRecord:
    r = db.get(HealthRecord, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Record not found")
    return r


@router.get("/records", response_model=list[RecordOut])
def list_records(user: CurrentUser, db: DB, record_type: str | None = Query(default=None)):
    q = select(HealthRecord).where(HealthRecord.user_id == user.id)
    if record_type:
        q = q.where(HealthRecord.record_type == record_type)
    return db.scalars(q.order_by(HealthRecord.record_date.desc(), HealthRecord.created_at.desc())).all()


@router.post("/records", response_model=RecordOut, status_code=status.HTTP_201_CREATED)
def create_record(body: RecordIn, user: CurrentUser, db: DB):
    r = HealthRecord(user_id=user.id, **body.model_dump())
    db.add(r)
    db.commit()
    return r


@router.put("/records/{rid}", response_model=RecordOut)
def update_record(rid: str, body: RecordIn, user: CurrentUser, db: DB):
    r = _own_record(db, user, rid)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return r


@router.delete("/records/{rid}", status_code=204)
def delete_record(rid: str, user: CurrentUser, db: DB):
    db.delete(_own_record(db, user, rid))
    db.commit()


# ---- Timeline -----------------------------------------------------------------------------------
@router.get("/timeline", response_model=list[TimelineEvent])
def timeline(user: CurrentUser, db: DB, limit: int = Query(default=50, ge=1, le=200)):
    """Chronological view merging records, confirmed prescriptions and emergency alerts."""
    events: list[TimelineEvent] = []
    for r in db.scalars(select(HealthRecord).where(HealthRecord.user_id == user.id)):
        events.append(TimelineEvent(
            id=r.id, kind="record", title=r.title, subtitle=r.record_type.replace("_", " ").title(),
            at=datetime.combine(r.record_date, time(12, 0), tzinfo=timezone.utc),
        ))
    for p in db.scalars(select(Prescription).where(Prescription.user_id == user.id, Prescription.status == "confirmed")):
        names = [i.medicine_name for i in p.items if i.user_confirmed and i.medicine_name]
        events.append(TimelineEvent(
            id=p.id, kind="prescription", title="Prescription confirmed",
            subtitle=", ".join(names[:4]) + ("…" if len(names) > 4 else ""), at=p.confirmed_at or p.created_at,
        ))
    for e in db.scalars(select(EmergencyEvent).where(EmergencyEvent.user_id == user.id)):
        events.append(TimelineEvent(
            id=e.id, kind="emergency", title="Emergency guidance shown",
            subtitle="Red-flag symptoms were detected in a message" if e.trigger != "manual" else "Emergency screen opened",
            at=e.created_at,
        ))
    events.sort(key=lambda e: e.at, reverse=True)
    return events[:limit]
