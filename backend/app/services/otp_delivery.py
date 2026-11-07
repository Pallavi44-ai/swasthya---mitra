"""Delivers one-time codes. REAL providers only in production:
  email → SMTP server (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)
  sms   → Twilio Programmable Messaging (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM)

The 'console' provider just writes the code to the server log so a developer can sign in locally
without an SMTP/SMS account. It is REFUSED when APP_ENV=production. The verification logic itself
(hashing, expiry, attempt limits) is identical for every provider.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
OUTBOX: list[dict] = []  # populated only when APP_ENV=test, so tests can read the code that was "sent"

SUBJECTS = {
    "register_verify": "Confirm your Swasthya Mitra account",
    "login": "Your Swasthya Mitra login code",
    "password_reset": "Reset your Swasthya Mitra password",
    "phone_verify": "Confirm your phone number",
}


class DeliveryError(Exception):
    """The code could not be delivered (provider misconfigured or unreachable)."""


def _text(code: str, purpose: str, minutes: int) -> str:
    return (f"Your Swasthya Mitra code is {code}.\n\nIt works for {minutes} minutes and only once. "
            "Never share this code with anyone – we will never ask for it by phone or message.\n"
            "If you did not ask for it, ignore this message and consider changing your password.")


def send_otp(channel: str, destination: str, code: str, purpose: str) -> None:
    s = get_settings()
    minutes = s.otp_ttl_seconds // 60
    if channel == "email":
        if s.otp_email_provider == "smtp":
            return _send_smtp(destination, SUBJECTS.get(purpose, "Your code"), _text(code, purpose, minutes))
        return _console(channel, destination, code, purpose)
    if channel == "sms":
        if s.otp_sms_provider == "twilio":
            return _send_twilio(destination, f"Swasthya Mitra code: {code}. Valid {minutes} min. Do not share it.")
        return _console(channel, destination, code, purpose)
    raise DeliveryError("Unknown channel")


def _console(channel: str, destination: str, code: str, purpose: str) -> None:
    s = get_settings()
    if s.is_production:
        raise DeliveryError("OTP delivery is not configured. Set the SMTP/Twilio provider variables.")
    if s.app_env == "test":
        OUTBOX.append({"channel": channel, "to": destination, "code": code, "purpose": purpose})
        return
    log.warning("DEV-ONLY OTP (console provider) purpose=%s channel=%s to=%s code=%s", purpose, channel, destination, code)


def _send_smtp(to: str, subject: str, body: str) -> None:
    s = get_settings()
    if not (s.smtp_host and s.smtp_from):
        raise DeliveryError("SMTP is not configured")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        log.error("SMTP delivery failed: %s", type(exc).__name__)  # never log the message/code
        raise DeliveryError("Email could not be sent") from exc


def _send_twilio(to: str, body: str, transport=None) -> None:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from):
        raise DeliveryError("Twilio is not configured")
    try:
        r = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
            data={"To": to, "From": s.twilio_from, "Body": body}, auth=(s.twilio_account_sid, s.twilio_auth_token), timeout=15,
        )
    except httpx.HTTPError as exc:
        log.error("Twilio request failed: %s", type(exc).__name__)
        raise DeliveryError("SMS could not be sent") from exc
    if r.status_code >= 300:
        log.error("Twilio rejected the message: HTTP %s", r.status_code)
        raise DeliveryError("SMS could not be sent")
