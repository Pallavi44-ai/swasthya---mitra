from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Language = Literal["en", "hi", "kn", "te"]


COMMON_PASSWORDS = {
    "password1", "password123", "pass1234", "qwerty123", "abc12345", "12345678a", "welcome123", "iloveyou1", "admin1234",
    "letmein123", "india12345", "india123", "test1234", "changeme1", "password12", "qwertyuiop1", "swasthya123",
}


def normalise_phone(v: str) -> str:
    v = re.sub(r"[\s\-()]", "", v)
    if re.fullmatch(r"[6-9]\d{9}", v):  # bare Indian mobile number
        v = "+91" + v
    elif re.fullmatch(r"91[6-9]\d{9}", v):
        v = "+" + v
    if not re.fullmatch(r"\+\d{10,15}", v):
        raise ValueError("Enter a mobile number with country code, for example +919876543210")
    return v


def check_password_strength(v: str) -> str:
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("Password must contain at least one letter and one digit")
    if len(v.encode()) > 72:
        raise ValueError("Password too long")
    if v.lower() in COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose another")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)
    preferred_language: Language = "en"
    phone: str | None = Field(default=None, max_length=20)
    mfa_channel: Literal["email", "sms"] = "email"  # where login codes are sent
    accepted_disclaimer: bool
    consents: dict[str, bool] = Field(default_factory=dict)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        return check_password_strength(v)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else None

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class UserOut(BaseModel):
    id: str
    email_verified: bool = False
    phone_verified: bool = False
    mfa_channel: Literal["email", "sms"] = "email"
    email: EmailStr
    full_name: str
    preferred_language: Language
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_language: Language | None = None
    timezone: str | None = Field(default=None, max_length=64)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        return check_password_strength(v)


class ConsentUpdate(BaseModel):
    consents: dict[str, bool]


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=72)


class MfaSendIn(BaseModel):
    challenge_id: str = Field(max_length=40)


class MfaVerifyIn(BaseModel):
    challenge_id: str = Field(max_length=40)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    challenge_id: str = Field(max_length=40)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        return check_password_strength(v)


class PhoneIn(BaseModel):
    phone: str
    password: str = Field(max_length=72)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        return normalise_phone(v)


class ChannelIn(BaseModel):
    channel: Literal["email", "sms"]
    password: str = Field(max_length=72)
