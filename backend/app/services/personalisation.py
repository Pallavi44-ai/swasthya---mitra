"""Personalisation layer (report §3.2): combines profile, history and current medicines as LLM context.
Used ONLY when the user has granted the 'health_data_personalisation' consent."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HealthProfile, Prescription, PrescriptionItem, User


def build_context(db: Session, user: User) -> tuple[str, str]:
    """Return (context_text_for_prompt, text_of_user_confirmed_medicines_for_guard)."""
    parts: list[str] = []
    p = db.get(HealthProfile, user.id)
    if p:
        if p.date_of_birth:
            t = date.today()
            age = t.year - p.date_of_birth.year - ((t.month, t.day) < (p.date_of_birth.month, p.date_of_birth.day))
            parts.append(f"Age: {age}")
        if p.sex:
            parts.append(f"Sex: {p.sex}")
        if p.conditions:
            parts.append("Known conditions: " + ", ".join(p.conditions))
        if p.allergies:
            parts.append("Allergies: " + ", ".join(p.allergies))
    meds = db.scalars(
        select(PrescriptionItem)
        .join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
        .where(Prescription.user_id == user.id, Prescription.status == "confirmed", PrescriptionItem.user_confirmed.is_(True))
        .limit(20)
    ).all()
    med_lines = [
        " ".join(x for x in (i.medicine_name, i.strength, i.dosage_instruction) if x) for i in meds if i.medicine_name
    ]
    if med_lines:
        parts.append("Medicines the user confirmed from their prescriptions: " + "; ".join(med_lines))
    return ("\n".join(parts), "\n".join(med_lines))
