from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RecordType = Literal["visit", "lab_report", "vaccination", "vitals", "condition", "note"]
BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}


def _clean_list(v: list[str] | None) -> list[str] | None:
    if v is None:
        return None
    out = []
    for item in v:
        item = item.strip()
        if item and item.lower() not in {o.lower() for o in out}:
            out.append(item[:80])
    return out[:50]


class ProfileIn(BaseModel):
    date_of_birth: date | None = None
    sex: Literal["female", "male", "other"] | None = None
    blood_group: str | None = None
    height_cm: float | None = Field(default=None, gt=30, lt=260)
    weight_kg: float | None = Field(default=None, gt=2, lt=400)
    allergies: list[str] | None = None
    conditions: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("date_of_birth")
    @classmethod
    def not_future(cls, v: date | None) -> date | None:
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("Invalid date of birth")
        return v

    @field_validator("blood_group")
    @classmethod
    def valid_bg(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if v not in BLOOD_GROUPS:
            raise ValueError("Invalid blood group")
        return v

    @field_validator("allergies", "conditions")
    @classmethod
    def clean(cls, v):
        return _clean_list(v)


class ProfileOut(ProfileIn):
    model_config = {"from_attributes": True}
    age: int | None = None


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=20)
    relationship: str | None = Field(default=None, max_length=50)
    is_primary: bool = False

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        v = re.sub(r"[\s\-()]", "", v)
        if not re.fullmatch(r"\+?\d{5,15}", v):
            raise ValueError("Enter a valid phone number (digits, optional leading +)")
        return v


class ContactOut(ContactIn):
    id: str


class RecordIn(BaseModel):
    record_type: RecordType
    title: str = Field(min_length=1, max_length=200)
    record_date: date
    details: str | None = Field(default=None, max_length=5000)

    @field_validator("record_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Record date cannot be in the future")
        return v


class RecordOut(RecordIn):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class TimelineEvent(BaseModel):
    id: str
    kind: Literal["record", "prescription", "emergency", "profile"]
    title: str
    subtitle: str | None = None
    at: datetime
