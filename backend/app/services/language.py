"""Language detection (DFD 2.0). Script-based: reliable for Devanagari / Kannada / Telugu text.

Limitation (documented): romanised Hindi/Kannada/Telugu ("Hinglish") is detected as English, so the
user's saved language preference is used as a tie-breaker by callers.
"""
from __future__ import annotations

SUPPORTED = ("en", "hi", "kn", "te")
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada", "te": "Telugu"}
SPEECH_LOCALES = {"en": "en-IN", "hi": "hi-IN", "kn": "kn-IN", "te": "te-IN"}

_RANGES = {
    "hi": (0x0900, 0x097F),
    "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF),
}


def detect_language(text: str, fallback: str = "en") -> str:
    counts = {k: 0 for k in _RANGES}
    latin = 0
    for ch in text:
        cp = ord(ch)
        for lang, (lo, hi) in _RANGES.items():
            if lo <= cp <= hi:
                counts[lang] += 1
                break
        else:
            if ch.isascii() and ch.isalpha():
                latin += 1
    best = max(counts, key=counts.get)
    if counts[best] and counts[best] >= max(2, latin * 0.5):
        return best
    if latin:
        return "en" if fallback not in SUPPORTED or fallback == "en" or latin >= 3 else fallback
    return fallback if fallback in SUPPORTED else "en"
