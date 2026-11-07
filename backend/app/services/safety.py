"""Safety & Emergency module (report module 6). Runs BEFORE any LLM call on every request.

Deterministic, offline, auditable. The LLM can only *add* an escalation (see chat_service); it can
never remove one raised here. The design does not claim to detect every emergency – the absence of
a flag is never presented to the user as proof of safety.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "red_flags.json"

EMERGENCY_NUMBERS = [
    {"label": "Ambulance / Emergency", "number": "108", "kind": "emergency"},
]
SELF_HARM_NUMBERS = [
    {"label": "Tele-MANAS (free mental-health helpline, 24x7)", "number": "14416", "kind": "helpline"},
    {"label": "Ambulance / Emergency", "number": "108", "kind": "emergency"},
]

EMERGENCY_TEXT = {
    "en": "This may be an emergency. Call 108 now. If someone is with you, ask them to stay beside you. Please do not wait for an online answer.",
    "hi": "यह आपातकाल हो सकता है। अभी 108 पर कॉल करें। अगर कोई आपके साथ है तो उसे अपने पास रहने को कहें। ऑनलाइन जवाब का इंतज़ार न करें।",
    "kn": "ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಆಗಿರಬಹುದು. ಈಗಲೇ 108 ಕ್ಕೆ ಕರೆ ಮಾಡಿ. ನಿಮ್ಮ ಜೊತೆ ಯಾರಾದರೂ ಇದ್ದರೆ ಅವರನ್ನು ಹತ್ತಿರ ಇರಲು ಹೇಳಿ. ಆನ್‌ಲೈನ್ ಉತ್ತರಕ್ಕಾಗಿ ಕಾಯಬೇಡಿ.",
    "te": "ఇది అత్యవసర పరిస్థితి కావచ్చు. వెంటనే 108 కు కాల్ చేయండి. మీతో ఎవరైనా ఉంటే వారిని దగ్గరే ఉండమని చెప్పండి. ఆన్‌లైన్ సమాధానం కోసం వేచి ఉండకండి.",
}
SELF_HARM_TEXT = {
    "en": "You are not alone, and help is available right now. Please call Tele-MANAS on 14416 (free, 24x7) or call 108 if you are in immediate danger. If someone is nearby, please tell them how you feel.",
    "hi": "आप अकेले नहीं हैं, मदद अभी उपलब्ध है। कृपया Tele-MANAS 14416 (मुफ़्त, 24x7) पर कॉल करें, या तुरंत खतरे में हों तो 108 पर कॉल करें। अगर कोई पास है तो उसे अपनी बात बताइए।",
    "kn": "ನೀವು ಒಬ್ಬಂಟಿಯಲ್ಲ, ಸಹಾಯ ಈಗಲೇ ಲಭ್ಯವಿದೆ. ದಯವಿಟ್ಟು Tele-MANAS 14416 (ಉಚಿತ, 24x7) ಗೆ ಕರೆ ಮಾಡಿ, ಅಥವಾ ತಕ್ಷಣದ ಅಪಾಯದಲ್ಲಿದ್ದರೆ 108 ಕ್ಕೆ ಕರೆ ಮಾಡಿ. ಹತ್ತಿರ ಯಾರಾದರೂ ಇದ್ದರೆ ಅವರಿಗೆ ನಿಮ್ಮ ಮನಸ್ಸಿನ ಮಾತು ಹೇಳಿ.",
    "te": "మీరు ఒంటరి కాదు, సహాయం ఇప్పుడే అందుబాటులో ఉంది. దయచేసి Tele-MANAS 14416 (ఉచితం, 24x7) కు కాల్ చేయండి, లేదా తక్షణ ప్రమాదంలో ఉంటే 108 కు కాల్ చేయండి. దగ్గర ఎవరైనా ఉంటే వారికి మీ మనసులోని మాట చెప్పండి.",
}
URGENT_TEXT = {
    "en": "These symptoms may need a doctor's attention soon. Please see a doctor today if you can.",
    "hi": "इन लक्षणों में डॉक्टर को जल्दी दिखाना ज़रूरी हो सकता है। हो सके तो आज ही डॉक्टर से मिलें।",
    "kn": "ಈ ಲಕ್ಷಣಗಳಿಗೆ ವೈದ್ಯರ ಗಮನ ಬೇಗ ಬೇಕಾಗಬಹುದು. ಸಾಧ್ಯವಾದರೆ ಇಂದೇ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ.",
    "te": "ఈ లక్షణాలకు వైద్యుడి దృష్టి త్వరగా అవసరం కావచ్చు. వీలైతే ఈ రోజే వైద్యుడిని కలవండి.",
}


@dataclass
class SafetyResult:
    level: str = "none"  # none | urgent | emergency
    flags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    @property
    def is_emergency(self) -> bool:
        return self.level == "emergency"

    @property
    def is_self_harm(self) -> bool:
        return "self_harm" in self.categories


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFC", text).lower()
    t = t.replace("’", "'").replace("‘", "'").replace("‌", "").replace("‍", "")
    return re.sub(r"\s+", " ", t).strip()


@lru_cache
def _compiled() -> dict[str, list[tuple[dict, list[re.Pattern]]]]:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    out: dict[str, list] = {}
    for level in ("emergency", "urgent"):
        entries = []
        for flag in raw[level]:
            pats = [re.compile(p, re.IGNORECASE) for plist in flag["patterns"].values() for p in plist]
            entries.append((flag, pats))
        out[level] = entries
    return out


def assess(text: str) -> SafetyResult:
    """Check text against the red-flag lexicon in every supported language at once."""
    t = normalise(text)
    result = SafetyResult()
    compiled = _compiled()
    for level in ("emergency", "urgent"):
        for flag, pats in compiled[level]:
            if any(p.search(t) for p in pats):
                result.flags.append(flag["id"])
                result.categories.append(flag["category"])
                result.labels.append(flag["label"])
                if level == "emergency":
                    result.level = "emergency"
                elif result.level == "none":
                    result.level = "urgent"
    return result


def escalate(result: SafetyResult, new_level: str) -> SafetyResult:
    """Raise (never lower) the level, e.g. when the LLM judges the situation more serious."""
    order = {"none": 0, "urgent": 1, "emergency": 2}
    if order.get(new_level, 0) > order[result.level]:
        result.level = new_level
        result.flags.append(f"llm_{new_level}")
    return result


def emergency_message(result: SafetyResult, lang: str) -> str:
    lang = lang if lang in EMERGENCY_TEXT else "en"
    return (SELF_HARM_TEXT if result.is_self_harm else EMERGENCY_TEXT)[lang]


def urgent_message(lang: str) -> str:
    return URGENT_TEXT.get(lang, URGENT_TEXT["en"])


def numbers_for(result: SafetyResult) -> list[dict]:
    return SELF_HARM_NUMBERS if result.is_self_harm else EMERGENCY_NUMBERS
