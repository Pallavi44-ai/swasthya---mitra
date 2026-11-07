"""Medication Reminder module (report module 4): schedule generation, dose tracking, adherence."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import DoseLog, Prescription, PrescriptionItem, Reminder, User

MISSED_AFTER = timedelta(hours=3)
HORIZON_DAYS = 7


def tz_of(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except Exception:  # noqa: BLE001
        return ZoneInfo("Asia/Kolkata")


def local_today(user: User) -> date:
    return datetime.now(tz_of(user)).date()


def get_confirmed_item(db: Session, user: User, item_id: str) -> PrescriptionItem:
    """THE gate: reminders can only be created for a medicine line the user explicitly confirmed."""
    item = db.get(PrescriptionItem, item_id)
    p = db.get(Prescription, item.prescription_id) if item else None
    if not item or not p or p.user_id != user.id:
        raise HTTPException(404, "Medicine not found")
    if p.status != "confirmed" or not item.user_confirmed:
        raise HTTPException(409, "Reminders can only be created from medicines you have confirmed. Please review and confirm the prescription first.")
    if not item.dosage_instruction:
        raise HTTPException(409, "This medicine has no confirmed dosage instruction")
    return item


def ensure_doses(db: Session, user: User, reminder: Reminder, through: date) -> int:
    """Materialise DoseLog rows from start_date to `through` (idempotent)."""
    tz = tz_of(user)
    last = min(through, reminder.end_date) if reminder.end_date else through
    existing = {d for (d,) in db.execute(select(DoseLog.scheduled_at).where(DoseLog.reminder_id == reminder.id))}
    created, day = 0, reminder.start_date
    while day <= last:
        for hhmm in reminder.times:
            h, m = map(int, hhmm.split(":"))
            at = datetime.combine(day, time(h, m), tzinfo=tz).astimezone(timezone.utc)
            if at >= reminder.created_at - timedelta(minutes=1) and at not in existing:
                db.add(DoseLog(reminder_id=reminder.id, user_id=user.id, scheduled_at=at))
                created += 1
        day += timedelta(days=1)
    return created


def refresh(db: Session, user: User) -> None:
    """Extend schedules a week ahead and mark long-overdue pending doses as missed."""
    horizon = local_today(user) + timedelta(days=HORIZON_DAYS)
    for r in db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.active.is_(True))):
        ensure_doses(db, user, r, horizon)
    cutoff = datetime.now(timezone.utc) - MISSED_AFTER
    db.execute(update(DoseLog).where(DoseLog.user_id == user.id, DoseLog.status == "pending", DoseLog.scheduled_at < cutoff).values(status="missed"))
    db.commit()


def regenerate_future(db: Session, user: User, reminder: Reminder) -> None:
    """After a schedule edit: drop future untouched doses and rebuild."""
    db.execute(delete(DoseLog).where(DoseLog.reminder_id == reminder.id, DoseLog.status == "pending", DoseLog.scheduled_at >= datetime.now(timezone.utc)))
    db.flush()
    if reminder.active:
        ensure_doses(db, user, reminder, local_today(user) + timedelta(days=HORIZON_DAYS))


def adherence(db: Session, user: User, days: int) -> dict:
    tz = tz_of(user)
    today = local_today(user)
    start_local = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=tz)
    rows = db.scalars(select(DoseLog).where(DoseLog.user_id == user.id, DoseLog.scheduled_at >= start_local.astimezone(timezone.utc))).all()
    now = datetime.now(timezone.utc)
    per_day: dict[date, dict[str, int]] = {today - timedelta(days=i): {"taken": 0, "skipped": 0, "missed": 0} for i in range(days)}
    for d in rows:
        if d.status == "pending" or d.scheduled_at > now:
            continue
        key = d.scheduled_at.astimezone(tz).date()
        if key in per_day:
            per_day[key][d.status] += 1
    totals = {k: sum(v[k] for v in per_day.values()) for k in ("taken", "skipped", "missed")}
    due = sum(totals.values())
    return {
        "days": [{"date": k.isoformat(), **v} for k, v in sorted(per_day.items())],
        "taken": totals["taken"], "skipped": totals["skipped"], "missed": totals["missed"],
        "percent": round(100 * totals["taken"] / due) if due else None,
    }
