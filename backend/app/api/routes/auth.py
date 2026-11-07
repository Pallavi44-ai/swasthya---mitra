"""Authentication: registration with verification, password + MFA login, recovery, logout.

Login is ALWAYS two steps – password, then a second factor (one-time code by email/SMS, or a
registered biometric passkey). No session cookie is issued after the password step alone.
"""
from __future__ import annotations

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.core.security import (
    COOKIE_NAME, create_access_token, decode_access_token, hash_password, rate_limiter, verify_password,
)
from app.models import AuditLog, CONSENT_PURPOSES, User, WebAuthnCredential
from app.schemas.auth import (
    ForgotIn, LoginIn, MfaSendIn, MfaVerifyIn, PasswordChange, RegisterIn, ResetIn, UserOut,
)
from app.services import otp, sessions
from app.services.consent import current_consents, set_consents

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)

# Dummy hash so unknown-email logins take about as long as real ones (no timing oracle).
_DUMMY_HASH = hash_password("not-a-real-password-1")
GENERIC_LOGIN_ERROR = "Incorrect email or password"


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _start_session(response: Response, db, user: User, request: Request, method: str) -> None:
    s = get_settings()
    sess = sessions.create(db, user, request, method)
    response.set_cookie(
        COOKIE_NAME, create_access_token(user.id, user.token_version, sess.id),
        max_age=s.access_token_minutes * 60, httponly=True, secure=s.cookie_secure, samesite="lax", path="/",
    )
    db.add(AuditLog(user_id=user.id, action="login_success", detail=method))
    db.commit()


def _has_passkey(db, user: User) -> bool:
    return db.scalar(select(WebAuthnCredential.id).where(WebAuthnCredential.user_id == user.id).limit(1)) is not None


# ---- Registration ---------------------------------------------------------------------------
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, db: DB):
    """Step 1 of 2. Creates an UNVERIFIED account and sends a code. No session until the code is verified."""
    s = get_settings()
    if not body.accepted_disclaimer:
        raise HTTPException(422, "You must acknowledge that Swasthya Mitra is not a substitute for a doctor.")
    unknown = set(body.consents) - set(CONSENT_PURPOSES)
    if unknown:
        raise HTTPException(422, f"Unknown consent purpose(s): {sorted(unknown)}")
    if body.mfa_channel == "sms" and not body.phone:
        raise HTTPException(422, "Enter your mobile number to receive codes by SMS.")
    if body.mfa_channel == "sms" and not s.sms_otp_ready:
        raise HTTPException(422, "SMS codes are not available on this server. Please choose email.")
    rate_limiter.check(f"register:{_ip(request)}", 10, 3600)
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user and (user.email_verified or user.phone_verified):
        raise HTTPException(409, "An account with this email already exists. Try logging in or resetting your password.")
    if user:  # abandoned, never-verified registration: let the real owner start over
        user.password_hash, user.full_name = hash_password(body.password), body.full_name
    else:
        user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name, timezone=s.default_timezone)
        db.add(user)
    user.preferred_language, user.phone, user.mfa_channel = body.preferred_language, body.phone, body.mfa_channel
    db.add(AuditLog(user_id=user.id, action="register_started"))
    db.commit()
    set_consents(db, user.id, {k: v for k, v in body.consents.items()})  # only what the user explicitly ticked
    channel, dest = ("sms", user.phone) if body.mfa_channel == "sms" else ("email", user.email)
    ch = otp.create(db, user, "register_verify", channel, dest)
    return otp.send(db, ch)


@router.post("/register/verify", response_model=UserOut)
def register_verify(body: MfaVerifyIn, request: Request, response: Response, db: DB):
    ch = otp.get(db, body.challenge_id, ("register_verify",))
    otp.verify(db, ch, body.code)
    user = db.get(User, ch.user_id)
    if ch.channel == "sms":
        user.phone_verified = True
    else:
        user.email_verified = True
    db.commit()
    _start_session(response, db, user, request, "register")
    return user


# ---- Login (password → second factor) ---------------------------------------------------------
@router.post("/login")
def login(body: LoginIn, request: Request, db: DB):
    key = f"login:{_ip(request)}:{body.email.lower()}"
    rate_limiter.check(key, 8, 900)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not (user and ok and user.is_active):
        db.add(AuditLog(user_id=user.id if user else None, action="login_failed"))
        db.commit()
        raise HTTPException(401, GENERIC_LOGIN_ERROR)
    rate_limiter.reset(key)
    if not (user.email_verified or user.phone_verified):  # finish the sign-up first
        channel, dest = ("sms", user.phone) if user.mfa_channel == "sms" and user.phone else ("email", user.email)
        ch = otp.create(db, user, "register_verify", channel, dest)
        raise HTTPException(403, {"code": "verification_required", "message": "Please confirm your account with the code we send you.", **otp.send(db, ch)})
    channel, dest = otp.destination_for(user)
    ch = otp.create(db, user, "login", channel, dest)
    passkey = _has_passkey(db, user)
    if passkey:  # let the user pick biometric or code; don't send a code nobody asked for
        db.commit()
        st = otp.state(ch)
    else:
        st = otp.send(db, ch)
    return {"mfa_required": True, "methods": ["otp", "biometric"] if passkey else ["otp"], **st}


@router.post("/mfa/send")
def mfa_send(body: MfaSendIn, db: DB):
    """Send – or securely re-send – the code for a pending step (cooldown + send cap enforced)."""
    ch = otp.get(db, body.challenge_id, ("login", "register_verify", "password_reset", "phone_verify"))
    return otp.send(db, ch)


@router.post("/mfa/verify", response_model=UserOut)
def mfa_verify(body: MfaVerifyIn, request: Request, response: Response, db: DB):
    ch = otp.get(db, body.challenge_id, ("login",))
    try:
        otp.verify(db, ch, body.code)
    except HTTPException:
        db.add(AuditLog(user_id=ch.user_id, action="mfa_failed"))
        db.commit()
        raise
    user = db.get(User, ch.user_id)
    _start_session(response, db, user, request, "password+otp")
    return user


# ---- Password recovery ------------------------------------------------------------------------
@router.post("/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: DB):
    """Always answers the same way, so it cannot be used to discover which emails have accounts."""
    rate_limiter.check(f"forgot:{_ip(request)}", 10, 3600)
    rate_limiter.check(f"forgot:{body.email.lower()}", 5, 3600)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.is_active and (user.email_verified or user.phone_verified):
        channel, dest = otp.destination_for(user)
        ch = otp.create(db, user, "password_reset", channel, dest)
        try:
            st = otp.send(db, ch)
            # Same shape/wording as the decoy below, so the response cannot reveal whether the account exists.
            return {**st, "channel": "email", "destination_masked": "your registered email or phone",
                    "expires_in": get_settings().otp_ttl_seconds, "resend_in": get_settings().otp_resend_cooldown_seconds,
                    "message": "If an account exists, we have sent a code."}
        except HTTPException:
            pass  # fall through to the same generic answer
    return {"challenge_id": secrets.token_hex(16)[:32], "channel": "email", "destination_masked": "your registered email or phone",
            "otp_sent": True, "expires_in": get_settings().otp_ttl_seconds, "resend_in": get_settings().otp_resend_cooldown_seconds,
            "sends_left": get_settings().otp_max_sends - 1, "max_attempts": get_settings().otp_max_attempts,
            "message": "If an account exists, we have sent a code."}


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetIn, db: DB):
    ch = otp.get(db, body.challenge_id, ("password_reset",))
    otp.verify(db, ch, body.code)
    user = db.get(User, ch.user_id)
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # every existing session dies
    sessions.revoke_all(db, user.id)
    db.add(AuditLog(user_id=user.id, action="password_reset"))
    db.commit()


# ---- Session ------------------------------------------------------------------------------------
@router.post("/logout", status_code=204)
def logout(response: Response, db: DB, sm_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None):
    if sm_session:
        try:
            p = decode_access_token(sm_session)
            sessions.revoke(db, p.get("sid", ""), p["sub"])  # server-side revoke, not just cookie removal
        except HTTPException:
            pass
    response.delete_cookie(COOKIE_NAME, path="/")


@router.post("/logout-all", status_code=204)
def logout_all(response: Response, user: CurrentUser, db: DB):
    """Sign out of every device."""
    user.token_version += 1
    sessions.revoke_all(db, user.id)
    db.add(AuditLog(user_id=user.id, action="logout_all"))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChange, request: Request, response: Response, user: CurrentUser, db: DB):
    rate_limiter.check(f"chpw:{user.id}", 6, 900)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    sessions.revoke_all(db, user.id)
    db.add(AuditLog(user_id=user.id, action="password_change"))
    db.commit()
    _start_session(response, db, user, request, "password_change")  # keep THIS device signed in


@router.get("/me")
def me(user: CurrentUser, db: DB):
    return {"user": UserOut.model_validate(user), "consents": current_consents(db, user.id)}
