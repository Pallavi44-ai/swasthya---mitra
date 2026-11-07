"""Application settings. All secrets come from environment variables (.env) – never hard-coded."""
from __future__ import annotations

import json
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_env: str = "development"  # development | production | test
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'swasthya.db'}"
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    access_token_minutes: int = 480

    # Secrets – generated & persisted for local development only; REQUIRED in production.
    jwt_secret: str | None = None
    data_encryption_key: str | None = None

    # External AI services (optional – features degrade gracefully when absent)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_timeout_seconds: float = 40.0

    # Uploads
    upload_dir: str = str(BASE_DIR / "data" / "uploads")
    max_upload_mb: int = Field(default=8, ge=1, le=25)

    # Tesseract languages to use for OCR (must be installed on the host)
    ocr_languages: str = "eng"

    default_timezone: str = "Asia/Kolkata"

    # ---- MFA / OTP -------------------------------------------------------------------------
    otp_ttl_seconds: int = 600  # a code is valid for 10 minutes
    otp_max_attempts: int = 5  # wrong guesses allowed per code
    otp_resend_cooldown_seconds: int = 30
    otp_max_sends: int = 4  # first send + 3 resends per challenge
    challenge_max_age_seconds: int = 1800  # a pending login/registration step expires after 30 min
    # Delivery providers. 'console' (log the code) is for local development ONLY and is rejected in production.
    otp_email_provider: str = "console"  # smtp | console
    otp_sms_provider: str = "console"  # twilio | console
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from: str | None = None

    # ---- Sessions & biometric (WebAuthn / passkeys) ----------------------------------------
    session_idle_minutes: int = 60
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Swasthya Mitra"
    webauthn_origin: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def email_otp_ready(self) -> bool:
        if self.otp_email_provider == "smtp":
            return bool(self.smtp_host and self.smtp_from)
        return not self.is_production and self.otp_email_provider == "console"

    @property
    def sms_otp_ready(self) -> bool:
        if self.otp_sms_provider == "twilio":
            return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from)
        return not self.is_production and self.otp_sms_provider == "console"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def _dev_secrets() -> dict[str, str]:
    """Create/read throw-away secrets for local development (file is git-ignored)."""
    path = BASE_DIR / "data" / ".dev_secrets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return json.loads(path.read_text())
    data = {
        "jwt_secret": secrets.token_urlsafe(48),
        "data_encryption_key": Fernet.generate_key().decode(),
    }
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return data


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not (s.jwt_secret and s.data_encryption_key):
        if s.is_production:
            raise RuntimeError("JWT_SECRET and DATA_ENCRYPTION_KEY must be set in production.")
        dev = _dev_secrets()
        s.jwt_secret = s.jwt_secret or dev["jwt_secret"]
        s.data_encryption_key = s.data_encryption_key or dev["data_encryption_key"]
    if s.is_production and not s.email_otp_ready:
        raise RuntimeError("Production requires OTP_EMAIL_PROVIDER=smtp with SMTP_HOST and SMTP_FROM. OTP delivery is never simulated in production.")
    return s
