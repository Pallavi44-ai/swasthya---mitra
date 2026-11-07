"""Honest implementation status: what is configured and working on THIS server right now."""
from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.api.deps import DB
from app.core.config import get_settings
from app.db.session import engine
from app.models import KnowledgeChunk
from app.services.gemini import get_gemini

router = APIRouter(prefix="/system", tags=["system"])


def _tesseract() -> dict:
    exe = shutil.which("tesseract")
    if not exe:
        return {"available": False, "languages": []}
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10).stdout
        langs = [l.strip() for l in out.splitlines()[1:] if l.strip()]
    except Exception:  # noqa: BLE001
        langs = []
    return {"available": True, "languages": langs}


@router.get("/health")
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/status")
def status(db: DB):
    s = get_settings()
    g = get_gemini()
    chunks = db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0
    embedded = db.scalar(select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.embedding.is_not(None))) or 0
    tess = _tesseract()
    return {
        "environment": s.app_env,
        "database": engine.dialect.name,
        "components": [
            {"id": "auth", "name": "Authentication: password (bcrypt) + mandatory second factor, device sessions, password recovery", "state": "implemented"},
            {"id": "otp_email", "name": "OTP delivery by email (SMTP)",
             "state": "configured" if s.otp_email_provider == "smtp" and s.email_otp_ready else "needs_configuration",
             "note": "Provider: SMTP." if s.otp_email_provider == "smtp" and s.email_otp_ready else
                     ("DEV ONLY: codes are printed in the server log. Set OTP_EMAIL_PROVIDER=smtp + SMTP_* for real delivery (required in production)." if not s.is_production else "Production needs SMTP_* settings.")},
            {"id": "otp_sms", "name": "OTP delivery by SMS (Twilio)",
             "state": "configured" if s.otp_sms_provider == "twilio" and s.sms_otp_ready else "needs_configuration",
             "note": "Provider: Twilio." if s.otp_sms_provider == "twilio" and s.sms_otp_ready else
                     ("DEV ONLY: SMS codes are printed in the server log. Set OTP_SMS_PROVIDER=twilio + TWILIO_* for real SMS." if s.sms_otp_ready else "SMS is disabled until Twilio is configured.")},
            {"id": "biometric", "name": "Biometric sign-in (WebAuthn passkeys)", "state": "implemented",
             "note": f"Relying party: {s.webauthn_rp_id}, origin {s.webauthn_origin}. Needs HTTPS (or localhost) and a device with fingerprint/face/screen lock."},
            {"id": "encryption", "name": "Field-level encryption at rest (Fernet)", "state": "implemented"},
            {"id": "consent", "name": "Consent ledger enforced server-side", "state": "implemented"},
            {"id": "safety", "name": "Red-flag detection (rule-based, EN/HI/KN/TE)", "state": "implemented", "note": "Phrase lists need clinical & native-speaker review"},
            {"id": "rag", "name": "RAG retrieval (BM25 + embeddings)", "state": "implemented",
             "note": f"{chunks} knowledge chunks; {embedded} embedded. Content is starter material pending clinical review."},
            {"id": "gemini", "name": "Gemini multimodal LLM (chat, extraction, transcription, embeddings)",
             "state": "configured" if g.configured else "needs_configuration",
             "note": f"model {g.model}" if g.configured else "Set GEMINI_API_KEY. Chat falls back to retrieval-only answers until then."},
            {"id": "ocr", "name": "Local OCR (Tesseract)", "state": "implemented" if tess["available"] else "needs_configuration",
             "note": f"languages installed: {', '.join(tess['languages']) or 'none'}"},
            {"id": "prescriptions", "name": "Prescription analysis with confirmation gate", "state": "implemented"},
            {"id": "reminders", "name": "Medication reminders & adherence (in-app / browser notifications)", "state": "implemented",
             "note": "Alerts fire while the app is open. Background web-push is not implemented."},
            {"id": "voice", "name": "Voice input/output (browser Web Speech + Gemini transcription endpoint)", "state": "implemented",
             "note": "Browser voice quality for Kannada/Telugu depends on the device; server transcription needs Gemini."},
            {"id": "emergency", "name": "Emergency screen: 108, helpline, contacts, location text hand-off", "state": "implemented",
             "note": "No server-side SMS/calls. Calls and messages are opened on the user's own device."},
        ],
        "tesseract": tess,
        "gemini_configured": g.configured,
        "limitations": [
            "Not a medical device. No clinical validation has been performed.",
            "Not implemented (outside approved scope): appointment booking, doctor/admin roles, EHR integration.",
        ],
    }
