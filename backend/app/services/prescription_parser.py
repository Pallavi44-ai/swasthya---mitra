"""Rule-based prescription line parser (offline fallback) and a deterministic dosage explainer.

Principles (report §4.7): extract only what is visibly present, never guess a missing value, flag
anything missing or uncertain, and never modify instructions. The explainer re-states the *written*
instruction in simple words – it does not decide doses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FORM_WORDS = r"(?:tab(?:let)?s?|cap(?:sule)?s?|syp|syr(?:up)?|susp(?:ension)?|inj(?:ection)?|oint(?:ment)?|drops?|cream|gel|lotion|sachet|inhaler)"
STRENGTH = r"\d+(?:[.,]\d+)?\s?(?:mg|mcg|µg|g|ml|iu|%)"
FREQ_PATTERNS = [
    r"\b[0-3]\s?-\s?[0-3]\s?-\s?[0-3](?:\s?-\s?[0-3])?\b",  # 1-0-1 / 1-1-1-1
    r"\b(?:once|twice|thrice)\s+(?:a\s+|per\s+)?(?:day|daily)\b",
    r"\b(?:one|two|three|four)\s+times\s+(?:a\s+)?(?:day|daily)\b",
    r"\b(?:OD|BD|BID|TDS|TID|QID|HS|SOS|PRN|STAT)\b",
]
TIMING = r"(?:after (?:food|meals?|breakfast|lunch|dinner)|before (?:food|meals?|breakfast|lunch|dinner)|with (?:food|meals?|water|milk)|empty stomach|at night|bed ?time|morning|evening)"
DURATION = r"(?:(?:x|for)\s*\d+\s*(?:days?|d|weeks?|wks?|months?)\b|\d+\s*(?:days?|weeks?|months?)\b)"
SKIP_LINE = re.compile(r"^(dr\.?|rx|date|name|age|sex|patient|address|reg\b|phone|ph\b|signature|clinic|hospital|diagnosis|follow)", re.I)


@dataclass
class ParsedItem:
    medicine_name: str | None = None
    strength: str | None = None
    form: str | None = None
    dosage_instruction: str | None = None
    frequency_text: str | None = None
    duration_text: str | None = None
    line_conf: float = 0.0
    flags: list[str] = field(default_factory=list)


def _norm_form(w: str | None) -> str | None:
    if not w:
        return None
    w = w.lower().rstrip("s.")
    for k, v in (("tab", "tablet"), ("cap", "capsule"), ("sy", "syrup"), ("susp", "suspension"), ("inj", "injection"), ("oint", "ointment"), ("drop", "drops")):
        if w.startswith(k):
            return v
    return w


def parse_line(line: str, conf: float = 1.0) -> ParsedItem | None:
    text = re.sub(r"^\s*(?:\d{1,2}\s*[).:-]|[•*\-–])\s*", "", line).strip()
    if len(text) < 4 or SKIP_LINE.match(text):
        return None
    form_m = re.match(rf"^({FORM_WORDS}|[TC]\.)\s*[.\-:]?\s*", text, re.I)
    strength_m = re.search(STRENGTH, text, re.I)
    if not form_m and not strength_m:
        return None
    rest = text[form_m.end():] if form_m else text
    name_m = re.match(r"([A-Za-z][A-Za-z0-9\-]*(?:\s[A-Za-z][A-Za-z0-9\-]*){0,2}?)(?=\s*(?:\d|$|[-–:,(]|\b(?:once|twice|OD|BD|TDS)\b))", rest.strip())
    name = name_m.group(1).strip() if name_m else None
    if name and re.fullmatch(rf"{FORM_WORDS}", name, re.I):
        name = None
    if not name or len(name) < 3:
        return None
    item = ParsedItem(medicine_name=name, line_conf=conf)
    item.form = _norm_form(form_m.group(1)) if form_m and form_m.group(1).upper() not in ("T.", "C.") else (
        "tablet" if form_m and form_m.group(1).upper() == "T." else "capsule" if form_m else None)
    st = re.search(STRENGTH, rest, re.I)
    item.strength = re.sub(r"\s+", "", st.group(0)).replace(",", ".") if st else None
    after = rest[st.end():] if st else rest[name_m.end():]
    freq = None
    for pat in FREQ_PATTERNS:
        m = re.search(pat, after, re.I)
        if m:
            freq = m.group(0)
            break
    timing = re.search(TIMING, after, re.I)
    dur = re.search(DURATION, after, re.I)
    item.frequency_text = re.sub(r"\s+", "", freq) if freq and "-" in freq else freq
    item.duration_text = dur.group(0).strip() if dur else None
    instr_bits = [b for b in (item.frequency_text, timing.group(0) if timing else None) if b]
    item.dosage_instruction = " ".join(instr_bits) if instr_bits else None
    if not item.strength:
        item.flags.append("strength_not_found")
    if not item.dosage_instruction:
        item.flags.append("dosage_instruction_not_found")
    if not item.duration_text:
        item.flags.append("duration_not_found")
    if conf < 0.7:
        item.flags.append("low_ocr_confidence")
    return item


def parse_lines(lines: list[tuple[str, float]]) -> tuple[list[ParsedItem], str | None, str | None]:
    items, doctor, date_s = [], None, None
    for text, conf in lines:
        if not doctor:
            dm = re.match(r"^\s*(dr\.?\s+[A-Za-z .]{3,40})", text, re.I)
            if dm:
                doctor = dm.group(1).strip()
        if not date_s:
            dd = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b", text)
            if dd:
                date_s = dd.group(0)
        it = parse_line(text, conf)
        if it:
            items.append(it)
    return items, doctor, date_s


def completeness(i: ParsedItem | dict) -> float:
    g = (lambda k: i.get(k)) if isinstance(i, dict) else (lambda k: getattr(i, k))
    return 0.4 * bool(g("medicine_name")) + 0.4 * bool(g("dosage_instruction")) + 0.1 * bool(g("strength")) + 0.1 * bool(g("duration_text"))


# ---- deterministic "explain in simple words" --------------------------------------------------
SLOTS = {
    "en": ["Morning", "Afternoon", "Evening", "Night"],
    "hi": ["सुबह", "दोपहर", "शाम", "रात"],
    "kn": ["ಬೆಳಿಗ್ಗೆ", "ಮಧ್ಯಾಹ್ನ", "ಸಂಜೆ", "ರಾತ್ರಿ"],
    "te": ["ఉదయం", "మధ్యాహ్నం", "సాయంత్రం", "రాత్రి"],
}
TIMING_TXT = {
    "after food": {"en": "after food", "hi": "खाने के बाद", "kn": "ಊಟದ ನಂತರ", "te": "భోజనం తర్వాత"},
    "before food": {"en": "before food", "hi": "खाने से पहले", "kn": "ಊಟದ ಮೊದಲು", "te": "భోజనం ముందు"},
    "empty stomach": {"en": "on an empty stomach", "hi": "खाली पेट", "kn": "ಖಾಲಿ ಹೊಟ್ಟೆಯಲ್ಲಿ", "te": "ఖాళీ కడుపుతో"},
}
AS_NEEDED = {"en": "Only when needed, as written by your doctor.", "hi": "केवल ज़रूरत पड़ने पर, जैसा डॉक्टर ने लिखा है।", "kn": "ವೈದ್ಯರು ಬರೆದಂತೆ, ಅಗತ್ಯವಿದ್ದಾಗ ಮಾತ್ರ.", "te": "వైద్యుడు రాసినట్లు, అవసరమైనప్పుడు మాత్రమే."}
ABBR_TIMES = {"OD": 1, "BD": 2, "BID": 2, "TDS": 3, "TID": 3, "QID": 4, "HS": 1}
DEFAULT_TIMES = {1: ["08:00"], 2: ["08:00", "20:00"], 3: ["08:00", "14:00", "20:00"], 4: ["08:00", "12:00", "16:00", "20:00"]}


def explain_instruction(instruction: str | None, lang: str = "en") -> dict:
    """Return plain-language lines for a written instruction + *editable* suggested clock times.
    parsed=False means we could not understand it – the UI then shows the original text only."""
    lang = lang if lang in SLOTS else "en"
    if not instruction:
        return {"parsed": False, "lines": [], "suggested_times": [], "as_needed": False}
    t = instruction.strip()
    timing_key = next((k for k in TIMING_TXT if k in t.lower()), None)
    timing_txt = TIMING_TXT[timing_key][lang] if timing_key else None
    if re.search(r"\b(SOS|PRN)\b", t, re.I):
        return {"parsed": True, "lines": [AS_NEEDED[lang]], "suggested_times": [], "as_needed": True}
    m = re.search(r"\b([0-3])\s?-\s?([0-3])\s?-\s?([0-3])(?:\s?-\s?([0-3]))?\b", t)
    if m:
        counts = [int(x) for x in m.groups() if x is not None]
        if len(counts) == 3:
            idx, labels = [0, 1, 3], [SLOTS[lang][0], SLOTS[lang][1], SLOTS[lang][3]]
            times = ["08:00", "14:00", "21:00"]
        else:
            idx, labels = [0, 1, 2, 3], SLOTS[lang]
            times = ["08:00", "13:00", "18:00", "21:00"]
        lines = [f"{labels[i]}: {c}" + (f" ({timing_txt})" if timing_txt and c else "") for i, c in enumerate(counts)]
        return {"parsed": True, "lines": lines, "suggested_times": [times[i] for i, c in enumerate(counts) if c], "as_needed": False}
    ab = re.search(r"\b(OD|BD|BID|TDS|TID|QID|HS)\b", t, re.I)
    n = ABBR_TIMES.get(ab.group(1).upper()) if ab else None
    if n is None:
        w = re.search(r"\b(once|one time|twice|two times|thrice|three times|four times)\b", t, re.I)
        n = {"once": 1, "one time": 1, "twice": 2, "two times": 2, "thrice": 3, "three times": 3, "four times": 4}.get(w.group(1).lower()) if w else None
    if n:
        txt = {"en": f"{n} time(s) a day", "hi": f"दिन में {n} बार", "kn": f"ದಿನಕ್ಕೆ {n} ಬಾರಿ", "te": f"రోజుకు {n} సార్లు"}[lang]
        times = ["21:00"] if ab and ab.group(1).upper() == "HS" else DEFAULT_TIMES[n]
        return {"parsed": True, "lines": [txt + (f" ({timing_txt})" if timing_txt else "")], "suggested_times": times, "as_needed": False}
    return {"parsed": False, "lines": [], "suggested_times": [], "as_needed": False}
