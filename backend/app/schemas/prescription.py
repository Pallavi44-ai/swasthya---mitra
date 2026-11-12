from __future__ import annotations

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    # Added by the Prescription Analyzer. All optional: records created before it simply return the defaults.
    verification_status: Literal["clear", "check", "unclear"] = "check"  # "clear" still needs the user's confirmation
    raw_text: str | None = None              # the line as written (kept so the user can compare with the paper)
    uncertainty_note: str | None = None      # why the reader was unsure
    additional_instructions: str | None = None


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
    patient: dict | None = None
    prescriber: dict | None = None
    diagnosis: str | None = None             # only if explicitly written on the prescription
    full_transcription: str | None = None
    ai_warnings: list[str] = []


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


class ImpactOut(BaseModel):
    """What removing a prescription would also remove. Read-only: asking never deletes anything."""
    status: str
    medicines: int
    reminders: int
    active_reminders: int
    doses_logged: int       # taken / skipped / missed history that adherence figures are built from
    doses_taken: int
    in_timeline: bool       # confirmed prescriptions appear on the health timeline
    has_photo: bool


class ConfirmIn(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=30)
    acknowledged: bool  # "I checked these details against my prescription"


# ---- Strict validation of what the vision model returns -----------------------------------------------------
# The model's JSON is never trusted as-is: every field is coerced to a safe type and length, bad values become
# None (never guessed), and a malformed medicine line is dropped instead of breaking the whole prescription.
def _text(v, n: int) -> str | None:
    if not isinstance(v, str):
        return None
    v = " ".join(v.split())
    return v[:n] or None


class AiMedicine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    strength: str | None = None
    form: str | None = None
    dosage_instruction: str | None = None
    frequency: str | None = None
    duration: str | None = None
    additional_instructions: str | None = None
    raw_text: str | None = None
    uncertainty_note: str | None = None
    confidence: float = 0.5
    unclear_fields: list[str] = []

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        return _text(v, 120)

    @field_validator("strength", "dosage_instruction", "additional_instructions", mode="before")
    @classmethod
    def _t200(cls, v):
        return _text(v, 200)

    @field_validator("form", mode="before")
    @classmethod
    def _t30(cls, v):
        return _text(v, 30)

    @field_validator("frequency", "duration", mode="before")
    @classmethod
    def _t60(cls, v):
        return _text(v, 60)

    @field_validator("raw_text", "uncertainty_note", mode="before")
    @classmethod
    def _t300(cls, v):
        return _text(v, 300)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        # bool is a subclass of int; strings and out-of-range numbers are not a confidence – fall back to "unsure"
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            return 0.5
        return float(v)

    @field_validator("unclear_fields", mode="before")
    @classmethod
    def _unclear(cls, v):
        return [t for t in (_text(x, 30) for x in v[:6]) if t] if isinstance(v, list) else []


class AiParty(BaseModel):
    """Patient or prescriber details, only what is written. Every value is optional free text."""
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    age: str | None = None
    sex: str | None = None
    qualification: str | None = None
    registration_number: str | None = None
    clinic: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _t(cls, v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):  # an age written as a number
            v = str(v)
        return _text(v, 120)

    def as_dict(self) -> dict | None:
        d = {k: v for k, v in self.model_dump().items() if v}
        return d or None


class AiPrescription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    doctor_name: str | None = None
    prescribed_date: str | None = None
    legibility: Literal["good", "fair", "poor"] = "fair"
    patient: AiParty | None = None
    prescriber: AiParty | None = None
    diagnosis: str | None = None
    warnings: list[str] = []
    full_transcription: str | None = None

    @field_validator("doctor_name", mode="before")
    @classmethod
    def _doc(cls, v):
        return _text(v, 80)

    @field_validator("prescribed_date", mode="before")
    @classmethod
    def _date(cls, v):
        return _text(v, 20)

    @field_validator("legibility", mode="before")
    @classmethod
    def _leg(cls, v):
        return v if v in ("good", "fair", "poor") else "fair"

    @field_validator("diagnosis", mode="before")
    @classmethod
    def _dx(cls, v):
        return _text(v, 200)

    @field_validator("full_transcription", mode="before")
    @classmethod
    def _full(cls, v):
        return v.strip()[:4000] or None if isinstance(v, str) else None

    @field_validator("warnings", mode="before")
    @classmethod
    def _warn(cls, v):
        return [t for t in (_text(x, 200) for x in v[:8]) if t] if isinstance(v, list) else []

    @field_validator("patient", "prescriber", mode="before")
    @classmethod
    def _party(cls, v):
        return v if isinstance(v, dict) else None
