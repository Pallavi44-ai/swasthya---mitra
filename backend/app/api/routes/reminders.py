from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models import DoseLog, Prescription, PrescriptionItem, Reminder
from app.services import reminders as svc

router = APIRouter(prefix="/reminders", tags=["reminders"])
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ReminderIn(BaseModel):
    prescription_item_id: str
    times: list[str] = Field(min_length=1, max_length=6)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("times")
    @classmethod
    def valid_times(cls, v: list[str]) -> list[str]:
        if not all(HHMM.match(t) for t in v):
            raise ValueError("Times must be in HH:MM (24-hour) format")
        return sorted(set(v))


class ReminderPatch(BaseModel):
    times: list[str] | None = Field(default=None, min_length=1, max_length=6)
    end_date: date | None = None
    active: bool | None = None

    @field_validator("times")
    @classmethod
    def valid_times(cls, v):
        return ReminderIn.valid_times(v) if v else v


class DoseAction(BaseModel):
    status: Literal["taken", "skipped"]


def _reminder_out(db, r: Reminder) -> dict:
    it = db.get(PrescriptionItem, r.prescription_item_id)
    return {
        "id": r.id, "prescription_item_id": r.prescription_item_id, "medicine_name": it.medicine_name, "strength": it.strength,
        "dosage_instruction": it.dosage_instruction,  # copied verbatim from the confirmed item – never editable here
        "times": r.times, "start_date": r.start_date, "end_date": r.end_date, "active": r.active,
    }


def _dose_out(db, d: DoseLog, tz) -> dict:
    r = db.get(Reminder, d.reminder_id)
    it = db.get(PrescriptionItem, r.prescription_item_id)
    return {
        "id": d.id, "reminder_id": r.id, "scheduled_at": d.scheduled_at, "local_time": d.scheduled_at.astimezone(tz).strftime("%H:%M"),
        "status": d.status, "medicine_name": it.medicine_name, "strength": it.strength, "dosage_instruction": it.dosage_instruction,
    }


def _own_reminder(db, user, rid: str) -> Reminder:
    r = db.get(Reminder, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Reminder not found")
    return r


@router.get("/eligible")
def eligible(user: CurrentUser, db: DB):
    """Confirmed medicines that don't yet have an active reminder."""
    have = {r.prescription_item_id for r in db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.active.is_(True)))}
    rows = db.scalars(
        select(PrescriptionItem).join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
        .where(Prescription.user_id == user.id, Prescription.status == "confirmed", PrescriptionItem.user_confirmed.is_(True))
    )
    return [
        {"prescription_item_id": i.id, "prescription_id": i.prescription_id, "medicine_name": i.medicine_name, "strength": i.strength,
         "dosage_instruction": i.dosage_instruction, "duration_text": i.duration_text}
        for i in rows if i.id not in have
    ]


@router.post("", status_code=201)
def create(body: ReminderIn, user: CurrentUser, db: DB):
    item = svc.get_confirmed_item(db, user, body.prescription_item_id)  # 404 / 409 gate
    if db.scalar(select(Reminder).where(Reminder.prescription_item_id == item.id, Reminder.active.is_(True))):
        raise HTTPException(409, "A reminder already exists for this medicine")
    start = body.start_date or svc.local_today(user)
    if body.end_date and body.end_date < start:
        raise HTTPException(422, "End date cannot be before the start date")
    if (body.end_date or start) - start > timedelta(days=365):
        raise HTTPException(422, "Reminders can run for at most one year")
    r = Reminder(user_id=user.id, prescription_item_id=item.id, times=body.times, start_date=start, end_date=body.end_date)
    db.add(r)
    db.flush()
    r.created_at = datetime.now(timezone.utc)
    svc.ensure_doses(db, user, r, svc.local_today(user) + timedelta(days=svc.HORIZON_DAYS))
    db.commit()
    return _reminder_out(db, r)


@router.get("")
def list_reminders(user: CurrentUser, db: DB):
    rows = db.scalars(select(Reminder).where(Reminder.user_id == user.id).order_by(Reminder.created_at.desc()))
    return [_reminder_out(db, r) for r in rows]


@router.patch("/{rid}")
def patch(rid: str, body: ReminderPatch, user: CurrentUser, db: DB):
    r = _own_reminder(db, user, rid)
    if body.times is not None:
        r.times = body.times
    if "end_date" in body.model_fields_set:
        if body.end_date and body.end_date < r.start_date:
            raise HTTPException(422, "End date cannot be before the start date")
        r.end_date = body.end_date
    if body.active is not None:
        r.active = body.active
    svc.regenerate_future(db, user, r)
    db.commit()
    return _reminder_out(db, r)


@router.delete("/{rid}", status_code=204)
def delete(rid: str, user: CurrentUser, db: DB):
    db.delete(_own_reminder(db, user, rid))
    db.commit()


@router.get("/today")
def today(user: CurrentUser, db: DB):
    svc.refresh(db, user)
    tz = svc.tz_of(user)
    d0 = svc.local_today(user)
    lo = datetime.combine(d0, time.min, tzinfo=tz).astimezone(timezone.utc)
    hi = datetime.combine(d0 + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    doses = db.scalars(select(DoseLog).where(DoseLog.user_id == user.id, DoseLog.scheduled_at >= lo, DoseLog.scheduled_at < hi).order_by(DoseLog.scheduled_at))
    return {"date": d0, "doses": [_dose_out(db, d, tz) for d in doses], "now": datetime.now(timezone.utc)}


@router.get("/due")
def due(user: CurrentUser, db: DB):
    """Pending doses whose time has arrived – polled by the app to raise notifications / spoken prompts."""
    svc.refresh(db, user)
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(DoseLog).where(DoseLog.user_id == user.id, DoseLog.status == "pending", DoseLog.scheduled_at <= now).order_by(DoseLog.scheduled_at))
    tz = svc.tz_of(user)
    return [_dose_out(db, d, tz) for d in rows]


@router.post("/doses/{did}")
def mark(did: str, body: DoseAction, user: CurrentUser, db: DB):
    d = db.get(DoseLog, did)
    if not d or d.user_id != user.id:
        raise HTTPException(404, "Dose not found")
    if d.scheduled_at > datetime.now(timezone.utc) + timedelta(hours=1):
        raise HTTPException(409, "This dose is not due yet")
    d.status, d.acted_at = body.status, datetime.now(timezone.utc)
    db.commit()
    return _dose_out(db, d, svc.tz_of(user))


@router.get("/adherence")
def adherence(user: CurrentUser, db: DB, days: int = Query(default=7, ge=1, le=90)):
    svc.refresh(db, user)
    return svc.adherence(db, user, days)
