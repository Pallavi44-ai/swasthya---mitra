from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class ItemOut(BaseModel):
    id: str
    medicine_name: str | None
    strength: str | None
    form: str | None
    dosage_instruction: str | None
    frequency_text: str | None
    duration_text: str | None
    confidence: float
    confidence_label: str  # high | medium | low
    needs_review: bool
    flags: list[str]
    edited_by_user: bool
    user_confirmed: bool


class PrescriptionOut(BaseModel):
    id: str
    status: str
    extraction_engine: str
    quality: dict | None
    warnings: list[str]
    doctor_name: str | None
    prescribed_date: date | None
    created_at: datetime
    confirmed_at: datetime | None
    has_image: bool
    items: list[ItemOut]
    message: str | None = None


class ItemIn(BaseModel):
    medicine_name: str = Field(min_length=2, max_length=120)
    strength: str | None = Field(default=None, max_length=40)
    form: str | None = Field(default=None, max_length=30)
    dosage_instruction: str | None = Field(default=None, max_length=200)
    frequency_text: str | None = Field(default=None, max_length=60)
    duration_text: str | None = Field(default=None, max_length=60)

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return v.strip() or None if isinstance(v, str) else v


class ConfirmIn(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=30)
    acknowledged: bool  # "I checked these details against my prescription"
