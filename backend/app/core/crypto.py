"""Field-level encryption at rest (Fernet / AES-128-CBC + HMAC) for sensitive health data."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().data_encryption_key.encode())


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as exc:  # wrong key or tampered data
        raise ValueError("Unable to decrypt stored data") from exc


class EncryptedText(TypeDecorator):
    """Text column transparently encrypted before hitting the database."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return None if value is None else encrypt_bytes(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return None if value is None else decrypt_bytes(value.encode()).decode()


class EncryptedJSON(TypeDecorator):
    """JSON-serialisable value stored as encrypted text."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        return None if value is None else encrypt_bytes(json.dumps(value).encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> Any:
        return None if value is None else json.loads(decrypt_bytes(value.encode()).decode())
