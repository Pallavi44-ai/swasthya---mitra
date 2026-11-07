"""Voice & Language module (report module 2) – server-side speech-to-text via Gemini audio input.

The browser also offers speech recognition and speech synthesis (Web Speech API), which the
frontend tries first; this endpoint is the multimodal-LLM path (browsers without SpeechRecognition,
or Kannada/Telugu where browser support varies). Text-to-speech is done in the browser.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.deps import DB, CurrentUser
from app.core.security import rate_limiter
from app.services.consent import require_consent
from app.services.gemini import GeminiError, GeminiUnavailable, get_gemini
from app.services.language import LANGUAGE_NAMES, SPEECH_LOCALES, detect_language

router = APIRouter(prefix="/voice", tags=["voice"])
ALLOWED = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/aac", "audio/flac"}
MAX_AUDIO_BYTES = 6 * 1024 * 1024


@router.get("/languages")
def languages():
    return [{"code": c, "name": n, "speech_locale": SPEECH_LOCALES[c]} for c, n in LANGUAGE_NAMES.items()]


@router.post("/transcribe")
async def transcribe(
    user: CurrentUser, db: DB, audio: Annotated[UploadFile, File()], language: Annotated[str, Form()] = "en",
):
    rate_limiter.check(f"stt:{user.id}", 30, 300)
    require_consent(db, user.id, "ai_processing", "Allow AI processing in Privacy settings to use server-side voice recognition.")
    if language not in LANGUAGE_NAMES:
        raise HTTPException(422, "Unsupported language")
    mime = (audio.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED:
        raise HTTPException(415, f"Unsupported audio type: {mime or 'unknown'}")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too long (max ~6 MB)")
    if len(data) < 800:
        raise HTTPException(422, "Audio is empty or too short")
    try:
        text = get_gemini().transcribe(data, mime, LANGUAGE_NAMES[language])
    except GeminiUnavailable:
        raise HTTPException(503, {"code": "not_configured", "message": "Server speech recognition is not configured. Use browser voice input or type."})
    except GeminiError:
        raise HTTPException(502, {"code": "upstream_error", "message": "Speech recognition failed. Please try again or type your question."})
    text = text.strip()
    if not text:
        raise HTTPException(422, {"code": "no_speech", "message": "I could not hear anything clearly. Please try again."})
    return {"text": text, "language": detect_language(text, language), "needs_confirmation": True}
