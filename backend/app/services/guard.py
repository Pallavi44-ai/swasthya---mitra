"""Output guard: enforces 'never invent dosages / never modify prescriptions' on LLM text.

Even though the system prompt forbids it, models can slip. Any sentence that states a quantity of
medicine which is not present in the retrieved sources or in the user's own confirmed prescription
text is removed before the answer is shown.
"""
from __future__ import annotations

import re

DOSE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s?(mg|mcg|µg|ug|g|ml|iu|units?|tablets?|tabs?|capsules?|caps|drops?|teaspoons?|tsp|tbsp|spoons?)\b",
    re.IGNORECASE,
)
CHANGE_RE = re.compile(
    r"\b(stop|discontinue|skip|double|increase|decrease|reduce|change|switch|start)\b[^.!?\n]{0,25}\b(your|the|his|her|that)\b[^.!?\n]{0,20}\b(medicine|medication|tablet|pill|dose|dosage|insulin|antibiotic)s?\b",
    re.IGNORECASE,
)
_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower().replace(",", "."))


def strip_unsupported_claims(answer: str, allowed_text: str) -> tuple[str, list[str]]:
    """Return (clean_answer, reasons_removed)."""
    allowed = {_norm(m.group(0)) for m in DOSE_RE.finditer(allowed_text)}
    kept, reasons = [], []
    for sent in _SENT_SPLIT.split(answer.strip()):
        if not sent.strip():
            continue
        bad_dose = [m for m in DOSE_RE.finditer(sent) if _norm(m.group(0)) not in allowed]
        if bad_dose:
            reasons.append("unsupported_dose")
            continue
        if CHANGE_RE.search(sent):
            reasons.append("medication_change_advice")
            continue
        kept.append(sent.strip())
    return " ".join(kept).strip(), reasons
