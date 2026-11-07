from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from rapidfuzz import fuzz
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.core.crypto import decrypt_bytes
from app.core.security import rate_limiter
from app.models import HealthProfile, Prescription, PrescriptionItem
from app.schemas.prescription import ConfirmIn, ItemIn, ItemOut, PrescriptionOut
from app.services import ocr, prescription_parser, prescription_service

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])

FAIL_MESSAGE = ("I could not read any medicines from this image. Please take a clearer, well-lit, straight-on photo, "
                "or ask your pharmacist or doctor to read it for you. You can also add a medicine by hand.")


def _label(c: float) -> str:
    return "high" if c >= 0.85 else "medium" if c >= 0.6 else "low"


def _out(p: Prescription) -> PrescriptionOut:
    items = [
        ItemOut(
            id=i.id, medicine_name=i.medicine_name, strength=i.strength, form=i.form, dosage_instruction=i.dosage_instruction,
            frequency_text=i.frequency_text, duration_text=i.duration_text, confidence=i.confidence,
            confidence_label=_label(i.confidence), needs_review=i.needs_review, flags=i.flags or [],
            edited_by_user=i.edited_by_user, user_confirmed=i.user_confirmed,
        ) for i in p.items
    ]
    return PrescriptionOut(
        id=p.id, status=p.status, extraction_engine=p.extraction_engine, quality=p.quality, warnings=p.warnings or [],
        doctor_name=p.doctor_name, prescribed_date=p.prescribed_date, created_at=p.created_at, confirmed_at=p.confirmed_at,
        has_image=bool(p.image_path), items=items, message=FAIL_MESSAGE if p.status == "failed" else None,
    )


def _own(db, user, pid: str) -> Prescription:
    p = db.get(Prescription, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Prescription not found")
    return p


def _own_item(p: Prescription, iid: str) -> PrescriptionItem:
    for i in p.items:
        if i.id == iid:
            return i
    raise HTTPException(404, "Medicine line not found")


def _editable(p: Prescription) -> None:
    if p.status not in ("extracted", "failed"):  # 'failed' = nothing readable → user may add medicines by hand
        raise HTTPException(409, "Only prescriptions awaiting review can be edited. Confirmed prescriptions are locked so reminders cannot silently change.")


@router.post("", response_model=PrescriptionOut, status_code=201)
async def upload(user: CurrentUser, db: DB, file: Annotated[UploadFile, File()]):
    rate_limiter.check(f"rx:{user.id}", 15, 600)
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"Image too large (max {get_settings().max_upload_mb} MB)")
    if not data:
        raise HTTPException(422, "Empty file")
    try:
        from starlette.concurrency import run_in_threadpool

        p = await run_in_threadpool(prescription_service.analyse, db, user, data)
    except ocr.ImageError as exc:
        raise HTTPException(422, str(exc))
    return _out(p)


@router.get("", response_model=list[PrescriptionOut])
def list_prescriptions(user: CurrentUser, db: DB):
    rows = db.scalars(select(Prescription).where(Prescription.user_id == user.id).order_by(Prescription.created_at.desc()).limit(50))
    return [_out(p) for p in rows]


@router.get("/{pid}", response_model=PrescriptionOut)
def get_prescription(pid: str, user: CurrentUser, db: DB):
    return _out(_own(db, user, pid))


@router.get("/{pid}/image")
def get_image(pid: str, user: CurrentUser, db: DB):
    p = _own(db, user, pid)
    if not p.image_path or not os.path.exists(p.image_path):
        raise HTTPException(404, "No stored image (you chose not to keep prescription photos)")
    with open(p.image_path, "rb") as fh:
        return Response(decrypt_bytes(fh.read()), media_type=p.image_mime or "image/jpeg")


@router.put("/{pid}/items/{iid}", response_model=PrescriptionOut)
def edit_item(pid: str, iid: str, body: ItemIn, user: CurrentUser, db: DB):
    p = _own(db, user, pid)
    _editable(p)
    it = _own_item(p, iid)
    for k, v in body.model_dump().items():
        setattr(it, k, v)
    it.edited_by_user, it.user_confirmed, it.needs_review = True, False, False  # user has now read & set the values
    db.commit()
    return _out(p)


@router.post("/{pid}/items", response_model=PrescriptionOut, status_code=201)
def add_item(pid: str, body: ItemIn, user: CurrentUser, db: DB):
    p = _own(db, user, pid)
    _editable(p)
    db.add(PrescriptionItem(
        prescription_id=p.id, position=len(p.items), confidence=1.0, needs_review=False, flags=["added_by_user"],
        edited_by_user=True, **body.model_dump(),
    ))
    if p.status == "failed":
        p.status = "extracted"
    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/{pid}/items/{iid}", response_model=PrescriptionOut)
def remove_item(pid: str, iid: str, user: CurrentUser, db: DB):
    p = _own(db, user, pid)
    _editable(p)
    db.delete(_own_item(p, iid))
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/{pid}/items/{iid}/explain")
def explain(pid: str, iid: str, user: CurrentUser, db: DB, lang: str = Query(default="en", pattern="^(en|hi|kn|te)$")):
    """Plain-language restatement of the *written* instruction + editable suggested reminder times."""
    it = _own_item(_own(db, user, pid), iid)
    return {"original": it.dosage_instruction, **prescription_parser.explain_instruction(it.dosage_instruction, lang)}


@router.post("/{pid}/confirm")
def confirm(pid: str, body: ConfirmIn, user: CurrentUser, db: DB):
    """The confirmation gate (use case 'Review Extracted Prescription Information'). Only items
    confirmed here can ever be used by the reminder module."""
    p = _own(db, user, pid)
    if p.status == "confirmed":
        raise HTTPException(409, "This prescription is already confirmed")
    if p.status != "extracted":
        raise HTTPException(409, "Nothing to confirm")
    if not body.acknowledged:
        raise HTTPException(422, "Please tick the box to confirm you have checked the details against your prescription.")
    chosen = [i for i in p.items if i.id in set(body.item_ids)]
    if len(chosen) != len(set(body.item_ids)):
        raise HTTPException(404, "One or more medicine lines were not found")
    problems = []
    for i in chosen:
        if not i.medicine_name:
            problems.append(f"A medicine name is missing")
        if not i.dosage_instruction:
            problems.append(f"{i.medicine_name or 'A medicine'}: dosage instruction is missing – please type it exactly as written on your prescription")
    if problems:
        raise HTTPException(422, {"code": "incomplete_items", "problems": problems})
    prof = db.get(HealthProfile, user.id)
    allergy_warnings = []
    for i in chosen:
        for a in (prof.allergies if prof and prof.allergies else []):
            if a.lower() in (i.medicine_name or "").lower() or fuzz.ratio(a.lower(), (i.medicine_name or "").lower()) >= 85:
                allergy_warnings.append(f"Your profile lists an allergy to “{a}”, and this prescription includes “{i.medicine_name}”. Please check with your doctor or pharmacist before taking it.")
    for i in p.items:
        i.user_confirmed = i.id in set(body.item_ids)
    p.status, p.confirmed_at = "confirmed", datetime.now(timezone.utc)
    db.commit()
    return {"prescription": _out(p), "allergy_warnings": allergy_warnings}


@router.delete("/{pid}", status_code=204)
def delete_prescription(pid: str, user: CurrentUser, db: DB):
    p = _own(db, user, pid)
    if p.image_path and os.path.exists(p.image_path):
        os.remove(p.image_path)
    db.delete(p)  # items → reminders → doses cascade
    db.commit()
