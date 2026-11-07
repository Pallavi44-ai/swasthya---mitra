"""Account security settings + biometric (passkey) enrolment and sign-in."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.routes.auth import _start_session
from app.core.config import get_settings
from app.core.security import rate_limiter, verify_password
from app.models import AuditLog, User, WebAuthnCredential
from app.schemas.auth import ChannelIn, MfaVerifyIn, PhoneIn, UserOut
from app.services import otp, passkeys, sessions

router = APIRouter(tags=["security"])


def _check_pw(user: User, password: str) -> None:
    rate_limiter.check(f"reauth:{user.id}", 8, 900)
    if not verify_password(password, user.password_hash):
        raise HTTPException(400, {"code": "wrong_password", "message": "Your password is not correct."})


# ---- Overview -------------------------------------------------------------------------------------
@router.get("/account/security")
def overview(user: CurrentUser, db: DB):
    sid = getattr(user, "_sid", None)
    creds = db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id).order_by(WebAuthnCredential.created_at))
    events = db.scalars(
        select(AuditLog).where(AuditLog.user_id == user.id, AuditLog.action.in_(
            ["login_success", "login_failed", "mfa_failed", "password_change", "password_reset", "logout_all"]
        )).order_by(AuditLog.created_at.desc()).limit(10)
    )
    s = get_settings()
    return {
        "email": user.email, "email_verified": user.email_verified,
        "phone_masked": otp.mask_destination("sms", user.phone) if user.phone else None, "phone_verified": user.phone_verified,
        "mfa_channel": user.mfa_channel, "sms_available": s.sms_otp_ready,
        "passkeys": [{"id": c.id, "name": c.name, "created_at": c.created_at, "last_used_at": c.last_used_at} for c in creds],
        "sessions": [{"id": x.id, "created_at": x.created_at, "last_seen_at": x.last_seen_at, "device": x.user_agent, "current": x.id == sid, "method": x.method} for x in sessions.active(db, user.id)],
        "recent_activity": [{"action": e.action, "at": e.created_at} for e in events],
        "session_idle_minutes": s.session_idle_minutes,
    }


@router.delete("/account/security/sessions/{sid}", status_code=204)
def revoke_session(sid: str, user: CurrentUser, db: DB):
    if not sessions.revoke(db, sid, user.id):
        raise HTTPException(404, "Session not found")


# ---- Phone number & code channel ------------------------------------------------------------------
@router.post("/account/security/phone")
def add_phone(body: PhoneIn, user: CurrentUser, db: DB):
    """Start verifying a new mobile number: a code is sent to THAT number."""
    _check_pw(user, body.password)
    if not get_settings().sms_otp_ready:
        raise HTTPException(422, "SMS codes are not available on this server.")
    ch = otp.create(db, user, "phone_verify", "sms", body.phone)
    return otp.send(db, ch)


@router.post("/account/security/phone/verify")
def verify_phone(body: MfaVerifyIn, user: CurrentUser, db: DB):
    ch = otp.get(db, body.challenge_id, ("phone_verify",), user_id=user.id)
    otp.verify(db, ch, body.code)
    user.phone, user.phone_verified = ch.destination, True
    db.add(AuditLog(user_id=user.id, action="phone_verified"))
    db.commit()
    return {"phone_masked": otp.mask_destination("sms", user.phone)}


@router.put("/account/security/channel")
def set_channel(body: ChannelIn, user: CurrentUser, db: DB):
    _check_pw(user, body.password)
    if body.channel == "sms" and not (user.phone and user.phone_verified):
        raise HTTPException(422, "Verify a mobile number first.")
    if body.channel == "email" and not user.email_verified:
        raise HTTPException(422, "Your email address is not verified.")
    user.mfa_channel = body.channel
    db.add(AuditLog(user_id=user.id, action="mfa_channel_changed", detail=body.channel))
    db.commit()
    return {"mfa_channel": user.mfa_channel}


# ---- Biometric / passkeys ---------------------------------------------------------------------------
class EnrolStart(BaseModel):
    password: str = Field(max_length=72)


class EnrolFinish(BaseModel):
    challenge_id: str = Field(max_length=40)
    credential: dict[str, Any]
    name: str | None = Field(default=None, max_length=60)


@router.post("/auth/webauthn/register/options")
def enrol_options(body: EnrolStart, user: CurrentUser, db: DB):
    _check_pw(user, body.password)
    ch = otp.create(db, user, "webauthn_enrol", "email", user.email)
    return {"challenge_id": ch.id, "options": passkeys.registration_options(db, user, ch)}


@router.post("/auth/webauthn/register/verify", status_code=201)
def enrol_verify(body: EnrolFinish, user: CurrentUser, db: DB):
    ch = otp.get(db, body.challenge_id, ("webauthn_enrol",), user_id=user.id)
    if ch.consumed_at:
        raise HTTPException(400, "This step was already used.")
    cred = passkeys.finish_registration(db, user, ch, body.credential, body.name)
    db.add(AuditLog(user_id=user.id, action="passkey_added"))
    db.commit()
    return {"id": cred.id, "name": cred.name}


@router.delete("/account/security/passkeys/{pid}", status_code=204)
def delete_passkey(pid: str, user: CurrentUser, db: DB):
    c = db.get(WebAuthnCredential, pid)
    if not c or c.user_id != user.id:
        raise HTTPException(404, "Passkey not found")
    db.delete(c)
    db.add(AuditLog(user_id=user.id, action="passkey_removed"))
    db.commit()


class LoginChallenge(BaseModel):
    challenge_id: str = Field(max_length=40)


class LoginFinish(LoginChallenge):
    credential: dict[str, Any]


def _pending_login(db, challenge_id: str):
    ch = otp.get(db, challenge_id, ("login",))
    from datetime import datetime, timedelta, timezone

    if ch.consumed_at or datetime.now(timezone.utc) - ch.created_at > timedelta(seconds=get_settings().challenge_max_age_seconds):
        raise HTTPException(400, {"code": "expired", "message": "This step has expired. Please log in again."})
    return ch, db.get(User, ch.user_id)


@router.post("/auth/webauthn/login/options")
def login_options(body: LoginChallenge, db: DB):
    """Second factor by biometric. Only reachable with a challenge that proves the PASSWORD step succeeded."""
    ch, user = _pending_login(db, body.challenge_id)
    return passkeys.authentication_options(db, user, ch)


@router.post("/auth/webauthn/login/verify", response_model=UserOut)
def login_verify(body: LoginFinish, request: Request, response: Response, db: DB):
    ch, user = _pending_login(db, body.challenge_id)
    passkeys.finish_authentication(db, user, ch, body.credential)
    _start_session(response, db, user, request, "password+biometric")
    return user
