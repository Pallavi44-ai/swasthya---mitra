"""Biometric / passkey (WebAuthn) support using the maintained `webauthn` library.
The browser asks the device for fingerprint / face / screen-lock (user verification is REQUIRED);
the server only ever sees a public key and signatures – never biometric data."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options, generate_registration_options, options_to_json,
    verify_authentication_response, verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, ResidentKeyRequirement, UserVerificationRequirement,
)

import json

from app.core.config import get_settings
from app.models import OtpChallenge, User, WebAuthnCredential


def _creds(db: Session, user_id: str) -> list[WebAuthnCredential]:
    return list(db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)))


def registration_options(db: Session, user: User, ch: OtpChallenge) -> dict:
    s = get_settings()
    opts = generate_registration_options(
        rp_id=s.webauthn_rp_id, rp_name=s.webauthn_rp_name, user_id=user.id.encode(), user_name=user.email,
        user_display_name=user.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(user_verification=UserVerificationRequirement.REQUIRED, resident_key=ResidentKeyRequirement.PREFERRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=c.credential_id) for c in _creds(db, user.id)],
    )
    ch.webauthn_challenge = bytes_to_base64url(opts.challenge)
    db.commit()
    return json.loads(options_to_json(opts))


def finish_registration(db: Session, user: User, ch: OtpChallenge, credential: dict, name: str | None) -> WebAuthnCredential:
    s = get_settings()
    try:
        v = verify_registration_response(
            credential=credential, expected_challenge=base64url_to_bytes(ch.webauthn_challenge or ""),
            expected_rp_id=s.webauthn_rp_id, expected_origin=s.webauthn_origin, require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001 – the library raises several specific errors; all mean "reject"
        raise HTTPException(400, {"code": "biometric_failed", "message": "Could not register this device. Please try again."}) from exc
    cred = WebAuthnCredential(user_id=user.id, credential_id=v.credential_id, public_key=v.credential_public_key, sign_count=v.sign_count, name=(name or "This device")[:60])
    db.add(cred)
    ch.consumed_at = datetime.now(timezone.utc)
    db.commit()
    return cred


def authentication_options(db: Session, user: User, ch: OtpChallenge) -> dict:
    creds = _creds(db, user.id)
    if not creds:
        raise HTTPException(400, {"code": "no_passkey", "message": "No biometric sign-in is set up for this account."})
    opts = generate_authentication_options(
        rp_id=get_settings().webauthn_rp_id, allow_credentials=[PublicKeyCredentialDescriptor(id=c.credential_id) for c in creds],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    ch.webauthn_challenge = bytes_to_base64url(opts.challenge)
    db.commit()
    return json.loads(options_to_json(opts))


def finish_authentication(db: Session, user: User, ch: OtpChallenge, credential: dict) -> WebAuthnCredential:
    s = get_settings()
    try:
        raw_id = base64url_to_bytes(credential.get("rawId") or credential.get("id") or "")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, {"code": "biometric_failed", "message": "Biometric check failed."}) from exc
    cred = next((c for c in _creds(db, user.id) if c.credential_id == raw_id), None)
    if not cred or not ch.webauthn_challenge:
        raise HTTPException(400, {"code": "biometric_failed", "message": "Biometric check failed."})
    try:
        v = verify_authentication_response(
            credential=credential, expected_challenge=base64url_to_bytes(ch.webauthn_challenge), expected_rp_id=s.webauthn_rp_id,
            expected_origin=s.webauthn_origin, credential_public_key=cred.public_key, credential_current_sign_count=cred.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, {"code": "biometric_failed", "message": "Biometric check failed."}) from exc
    cred.sign_count, cred.last_used_at = v.new_sign_count, datetime.now(timezone.utc)
    ch.consumed_at, ch.webauthn_challenge = datetime.now(timezone.utc), None  # single use
    db.commit()
    return cred
