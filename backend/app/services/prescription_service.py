"""Prescription Analysis module (report module 3, §4.7).

Pipeline: validate image → quality score → local OCR (Tesseract) → extraction
  (Gemini multimodal if configured + user consented, else rule-based parser) → grounding check of
every field against the OCR text → per-item confidence & flags → user review → explicit confirmation.

Nothing extracted here is ever used (e.g. for reminders) until the user confirms it.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import encrypt_bytes
from app.models import Prescription, PrescriptionItem, User
from app.services import ocr, prescription_parser as pp
from app.services.consent import current_consents
from app.services.gemini import GeminiError, get_gemini

log = logging.getLogger(__name__)
REVIEW_THRESHOLD = 0.85

EXTRACT_SYSTEM = """You read photographs of Indian medical prescriptions for a patient-safety application.
Extract ONLY what is clearly written. Rules:
- Never guess or complete a medicine name, strength or dose. If a field is unclear or absent, return null and list the field name in "unclear_fields".
- Copy dosage instructions exactly as written (for example "1-0-1 after food"). Do not convert or reinterpret them.
- Do not add medicines that are not written. Do not give medical advice.
- "confidence" is your honest 0-1 certainty that you read that medicine line correctly.
Return JSON only."""

EXTRACT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "doctor_name": {"type": "STRING", "nullable": True},
        "prescribed_date": {"type": "STRING", "nullable": True},
        "legibility": {"type": "STRING", "enum": ["good", "fair", "poor"]},
        "medicines": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING", "nullable": True}, "strength": {"type": "STRING", "nullable": True},
                    "form": {"type": "STRING", "nullable": True}, "dosage_instruction": {"type": "STRING", "nullable": True},
                    "frequency": {"type": "STRING", "nullable": True}, "duration": {"type": "STRING", "nullable": True},
                    "confidence": {"type": "NUMBER"}, "unclear_fields": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["name", "confidence"],
            },
        },
    },
    "required": ["medicines", "legibility"],
}


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            d = datetime.strptime(s.strip(), fmt).date()
            return d if date(2000, 1, 1) <= d <= date.today() else None
        except ValueError:
            continue
    return None


def _grounded(text: str | None, ocr_text: str) -> float:
    """How well does a value appear in the OCR text? 0..1 (token-set partial match)."""
    if not text or not ocr_text:
        return 0.0
    return fuzz.partial_ratio(text.lower(), ocr_text.lower()) / 100.0


def _from_gemini(img_bytes: bytes, ocr_res: ocr.OcrResult) -> tuple[list[dict], str | None, date | None, str]:
    hint = f"\n\nOCR text from a local engine (may contain errors, use only as a hint):\n{ocr_res.text[:2500]}" if ocr_res.text else ""
    import base64

    contents = [{"role": "user", "parts": [
        {"text": "Extract the medicines from this prescription image." + hint},
        {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(img_bytes).decode()}},
    ]}]
    data = get_gemini().generate_json(system=EXTRACT_SYSTEM, contents=contents, json_schema=EXTRACT_SCHEMA, temperature=0.0, max_tokens=2000)
    meds = data.get("medicines") if isinstance(data, dict) else None
    if not isinstance(meds, list):
        raise GeminiError("Unexpected extraction format")
    out = []
    for m in meds[:30]:
        if not isinstance(m, dict) or not (m.get("name") or "").strip():
            continue
        conf = m.get("confidence")
        conf = float(conf) if isinstance(conf, (int, float)) and 0 <= conf <= 1 else 0.5
        out.append({
            "medicine_name": m["name"].strip()[:120], "strength": _s(m.get("strength")), "form": _s(m.get("form"), 30),
            "dosage_instruction": _s(m.get("dosage_instruction")), "frequency_text": _s(m.get("frequency")),
            "duration_text": _s(m.get("duration")), "model_conf": conf, "unclear": [str(u) for u in (m.get("unclear_fields") or [])][:6],
        })
    return out, _s(data.get("doctor_name"), 80), _parse_date(data.get("prescribed_date")), str(data.get("legibility", "fair"))


def _s(v, n: int = 200) -> str | None:
    v = (v or "").strip() if isinstance(v, str) else None
    return v[:n] if v else None


def _score_items(raw: list[dict], ocr_res: ocr.OcrResult, source: str) -> list[dict]:
    """Attach confidence + flags. Confidence blends extractor certainty, OCR grounding and completeness."""
    scored = []
    for r in raw:
        flags = [f"unclear:{u}" for u in r.get("unclear", [])]
        comp = pp.completeness(r)
        if source == "gemini":
            if ocr_res.available and len(ocr_res.text) > 20:
                g_name = _grounded(r["medicine_name"], ocr_res.text)
                if g_name < 0.8:
                    flags.append("name_not_found_in_ocr_text")
                if r.get("dosage_instruction") and _grounded(r["dosage_instruction"], ocr_res.text) < 0.7:
                    flags.append("dosage_not_verified_in_ocr_text")
                conf = 0.4 * r["model_conf"] + 0.4 * g_name + 0.2 * comp
            else:
                flags.append("unverified_no_ocr_text")  # e.g. handwriting: nothing independent to cross-check
                conf = min(0.6, 0.6 * r["model_conf"] + 0.4 * comp)
        else:
            conf = 0.5 * r.get("line_conf", 0.0) + 0.5 * comp
        if not r.get("strength"):
            flags.append("strength_not_found")
        if not r.get("dosage_instruction"):
            flags.append("dosage_instruction_not_found")
        flags = sorted(set(flags + r.get("flags", [])))
        conf = round(max(0.0, min(conf, 1.0)), 2)
        scored.append({**{k: r.get(k) for k in ("medicine_name", "strength", "form", "dosage_instruction", "frequency_text", "duration_text")},
                       "confidence": conf, "flags": flags, "needs_review": conf < REVIEW_THRESHOLD or bool(flags)})
    return scored


def analyse(db: Session, user: User, data: bytes) -> Prescription:
    img = ocr.load_image(data)  # raises ImageError
    quality = ocr.assess_quality(img)
    ocr_res = ocr.run_ocr(img)
    consents = current_consents(db, user.id)
    warnings: list[str] = [f"image_{w}" for w in quality["warnings"]]
    if not ocr_res.available:
        warnings.append("local_ocr_unavailable")

    items, engine, doctor, pdate = [], "none", None, None
    g = get_gemini()
    if consents["ai_processing"] and g.configured:
        try:
            raw, doctor, pdate, legib = _from_gemini(ocr.to_jpeg_bytes(img), ocr_res)
            items, engine = _score_items(raw, ocr_res, "gemini"), "gemini+tesseract" if ocr_res.available else "gemini"
            if legib == "poor":
                warnings.append("model_reports_poor_legibility")
        except GeminiError as exc:
            log.warning("Gemini extraction failed, using local parser: %s", exc)
            warnings.append("ai_extraction_failed_used_local_parser")
    elif not consents["ai_processing"]:
        warnings.append("ai_consent_off_local_only")
    else:
        warnings.append("ai_not_configured_local_only")

    if not items and ocr_res.available:
        parsed, doctor2, date2, = pp.parse_lines([(l.text, l.conf) for l in ocr_res.lines])
        doctor, pdate = doctor or doctor2, pdate or _parse_date(date2)
        items = _score_items([{**vars(p)} for p in parsed], ocr_res, "rules")
        engine = "tesseract-rules"

    p = Prescription(
        user_id=user.id, status="extracted" if items else "failed", extraction_engine=engine,
        quality=quality, ocr_text=ocr_res.text or None, warnings=warnings, doctor_name=doctor, prescribed_date=pdate,
    )
    db.add(p)
    db.flush()
    for pos, it in enumerate(items):
        db.add(PrescriptionItem(prescription_id=p.id, position=pos, **it))
    if consents["store_prescription_images"]:
        d = os.path.join(get_settings().upload_dir, user.id)
        os.makedirs(d, mode=0o700, exist_ok=True)
        path = os.path.join(d, f"{p.id}.enc")
        with open(path, "wb") as fh:
            fh.write(encrypt_bytes(ocr.to_jpeg_bytes(img)))
        p.image_path, p.image_mime = path, "image/jpeg"
    db.commit()
    return p
