"""One-time-code challenges: generation, hashed storage, expiry, attempt limits, secure resend.

Security properties
 • Codes are 6 digits from `secrets` (CSPRNG) and are NEVER stored – only HMAC-SHA256(key, id:purpose:code).
 • Constant-time comparison (hmac.compare_digest).
 • A code expires after OTP_TTL_SECONDS and works once. A new code invalidates the previous one.
 • Max OTP_MAX_ATTEMPTS wrong guesses per code, then the code is dead until a (rate-limited) resend.
 • Resend: cooldown between sends and a cap on total sends per challenge; a pending step also has a hard max age.
 • Responses never reveal whether the code was close, and unknown ids look the same as wrong codes.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import OtpChallenge, User
from app.services import otp_delivery

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key() -> bytes:
    return hashlib.sha256(("otp-hmac:" + get_settings().jwt_secret).encode()).digest()


def hash_code(challenge_id: str, purpose: str, code: str) -> str:
    return hmac.new(_key(), f"{challenge_id}:{purpose}:{code}".encode(), hashlib.sha256).hexdigest()


def mask_destination(channel: str, dest: str) -> str:
    if channel == "email":
        name, _, dom = dest.partition("@")
        return f"{name[:1]}{'•' * max(len(name) - 1, 2)}@{dom}"
    return f"{'•' * max(len(dest) - 4, 4)}{dest[-4:]}"


def destination_for(user: User) -> tuple[str, str]:
    if user.mfa_channel == "sms" and user.phone and user.phone_verified:
        return "sms", user.phone
    return "email", user.email


def err(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message, **extra})


def create(db: Session, user: User, purpose: str, channel: str, destination: str) -> OtpChallenge:
    ch = OtpChallenge(user_id=user.id, purpose=purpose, channel=channel, destination=destination)
    db.add(ch)
    db.flush()
    return ch


def send(db: Session, ch: OtpChallenge) -> dict:
    """(Re)send a fresh code. Enforces cooldown, max sends and the challenge's maximum age."""
    s = get_settings()
    now = _now()
    if ch.consumed_at or now - ch.created_at > timedelta(seconds=s.challenge_max_age_seconds):
        raise err(400, "expired", "This step has expired. Please start again.")
    if ch.sends >= s.otp_max_sends:
        raise err(429, "too_many_sends", "Too many codes requested. Please start again in a few minutes.")
    if ch.last_sent_at:
        wait = s.otp_resend_cooldown_seconds - (now - ch.last_sent_at).total_seconds()
        if wait > 0:
            raise err(429, "resend_wait", f"Please wait {int(wait) + 1} seconds before asking for a new code.", retry_after=int(wait) + 1)
    code = f"{secrets.randbelow(10**6):06d}"
    try:
        otp_delivery.send_otp(ch.channel, ch.destination, code, ch.purpose)
    except otp_delivery.DeliveryError as exc:
        db.rollback()
        raise err(503, "delivery_failed", "We could not send the code. Please try again, or use another method.") from exc
    ch.code_hash = hash_code(ch.id, ch.purpose, code)
    ch.expires_at = now + timedelta(seconds=s.otp_ttl_seconds)
    ch.attempts, ch.sends, ch.last_sent_at = 0, ch.sends + 1, now
    db.commit()
    return state(ch)


def state(ch: OtpChallenge) -> dict:
    s = get_settings()
    now = _now()
    resend_in = 0
    if ch.last_sent_at:
        resend_in = max(0, int(s.otp_resend_cooldown_seconds - (now - ch.last_sent_at).total_seconds()) + 1)
    return {
        "challenge_id": ch.id, "channel": ch.channel, "destination_masked": mask_destination(ch.channel, ch.destination),
        "otp_sent": ch.code_hash is not None, "expires_in": max(0, int((ch.expires_at - now).total_seconds())) if ch.expires_at else 0,
        "resend_in": resend_in if ch.code_hash else 0, "sends_left": max(0, s.otp_max_sends - ch.sends),
        "max_attempts": s.otp_max_attempts,
    }


def get(db: Session, challenge_id: str, purposes: tuple[str, ...], user_id: str | None = None) -> OtpChallenge:
    ch = db.get(OtpChallenge, challenge_id) if challenge_id else None
    if not ch or ch.purpose not in purposes or (user_id and ch.user_id != user_id):
        raise err(400, "invalid_code", "That code is not correct.")  # same answer as a wrong code
    return ch


def verify(db: Session, ch: OtpChallenge, code: str) -> OtpChallenge:
    s = get_settings()
    now = _now()
    if ch.consumed_at:
        raise err(400, "invalid_code", "That code is not correct.")
    if now - ch.created_at > timedelta(seconds=s.challenge_max_age_seconds):
        raise err(400, "expired", "This step has expired. Please start again.")
    if not ch.code_hash or not ch.expires_at:
        raise err(400, "no_code", "No code has been sent yet. Ask for a code first.")
    if now > ch.expires_at:
        raise err(400, "expired", "This code has expired. Ask for a new one.", can_resend=ch.sends < s.otp_max_sends)
    if ch.attempts >= s.otp_max_attempts:
        raise err(429, "locked", "Too many wrong codes. Ask for a new code.", can_resend=ch.sends < s.otp_max_sends)
    ch.attempts += 1
    ok = hmac.compare_digest(ch.code_hash, hash_code(ch.id, ch.purpose, (code or "").strip()))
    if not ok:
        db.commit()
        left = s.otp_max_attempts - ch.attempts
        if left <= 0:
            raise err(429, "locked", "Too many wrong codes. Ask for a new code.", can_resend=ch.sends < s.otp_max_sends)
        raise err(400, "invalid_code", "That code is not correct.", attempts_left=left)
    ch.consumed_at, ch.code_hash = now, None  # single use; drop the hash too
    db.commit()
    return ch
