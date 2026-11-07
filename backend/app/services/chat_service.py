"""AI Companion orchestration (report modules 1 & 6, workflow Fig 3.3 / 4.3).

Order of operations for every message – the safety check ALWAYS precedes the LLM:
  1. language detection  →  2. red-flag safety check (emergency ⇒ deterministic answer, no LLM)
  3. intent routing      →  4. RAG retrieval  →  5. personalisation (if consented)
  6. multimodal LLM (if configured + consented) → 7. LLM urgency can only raise the level
  8. output guard (no invented doses)  →  9. localised disclaimer, sources, optional storage.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, EmergencyContact, EmergencyEvent, User
from app.schemas.chat import ChatIn, ChatOut, SafetyOut, Source
from app.services import companion, guard, personalisation, rag, safety
from app.db.types import utcnow
from app.services.consent import current_consents
from app.services.gemini import GeminiError, get_gemini
from app.services.language import LANGUAGE_NAMES, detect_language

log = logging.getLogger(__name__)

DISCLAIMER = {
    "en": "General information only – not a diagnosis or a substitute for a doctor.",
    "hi": "केवल सामान्य जानकारी – यह निदान या डॉक्टर का विकल्प नहीं है।",
    "kn": "ಸಾಮಾನ್ಯ ಮಾಹಿತಿ ಮಾತ್ರ – ಇದು ರೋಗನಿರ್ಣಯ ಅಥವಾ ವೈದ್ಯರ ಬದಲಿ ಅಲ್ಲ.",
    "te": "సాధారణ సమాచారం మాత్రమే – ఇది వ్యాధి నిర్ధారణ లేదా వైద్యుడికి ప్రత్యామ్నాయం కాదు.",
}
UNAVAILABLE = {
    "en": "I can't use the AI service right now, so I can't answer this reliably. Please ask a doctor or pharmacist. In an emergency call 108.",
    "hi": "अभी मैं AI सेवा का उपयोग नहीं कर पा रहा, इसलिए भरोसे से जवाब नहीं दे सकता। कृपया डॉक्टर या फ़ार्मासिस्ट से पूछें। आपातकाल में 108 पर कॉल करें।",
    "kn": "ಈಗ AI ಸೇವೆ ಬಳಸಲು ಸಾಧ್ಯವಿಲ್ಲ, ಆದ್ದರಿಂದ ವಿಶ್ವಾಸಾರ್ಹ ಉತ್ತರ ಕೊಡಲಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ವೈದ್ಯರು ಅಥವಾ ಫಾರ್ಮಸಿಸ್ಟ್ ಅವರನ್ನು ಕೇಳಿ. ತುರ್ತು ಸ್ಥಿತಿಯಲ್ಲಿ 108 ಕ್ಕೆ ಕರೆ ಮಾಡಿ.",
    "te": "ప్రస్తుతం AI సేవను ఉపయోగించలేకపోతున్నాను, కాబట్టి నమ్మకంగా సమాధానం ఇవ్వలేను. దయచేసి డాక్టర్ లేదా ఫార్మసిస్ట్‌ను అడగండి. అత్యవసర పరిస్థితిలో 108 కు కాల్ చేయండి.",
}
NO_INFO = {
    "en": "I don't have trusted information on that in my notes. Please ask a doctor or pharmacist.",
    "hi": "मेरे नोट्स में इसकी भरोसेमंद जानकारी नहीं है। कृपया डॉक्टर या फ़ार्मासिस्ट से पूछें।",
    "kn": "ನನ್ನ ಟಿಪ್ಪಣಿಗಳಲ್ಲಿ ಇದರ ವಿಶ್ವಾಸಾರ್ಹ ಮಾಹಿತಿ ಇಲ್ಲ. ದಯವಿಟ್ಟು ವೈದ್ಯರು ಅಥವಾ ಫಾರ್ಮಸಿಸ್ಟ್ ಅವರನ್ನು ಕೇಳಿ.",
    "te": "నా నోట్స్‌లో దీని గురించి నమ్మకమైన సమాచారం లేదు. దయచేసి డాక్టర్ లేదా ఫార్మసిస్ట్‌ను అడగండి.",
}
NAV = {
    "prescription": {
        "en": "You can scan a prescription on the Prescriptions page. I will read it and show what I found, and you confirm every medicine before anything else happens.",
        "hi": "आप प्रिस्क्रिप्शन पेज पर पर्चे की फ़ोटो डाल सकते हैं। मैं उसे पढ़कर जो मिला वह दिखाऊँगा, और आगे कुछ भी होने से पहले आप हर दवा की पुष्टि करेंगे।",
        "kn": "ನೀವು ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್ ಪುಟದಲ್ಲಿ ಚೀಟಿಯ ಫೋಟೋ ಹಾಕಬಹುದು. ನಾನು ಓದಿ ಸಿಕ್ಕಿದ ವಿವರಗಳನ್ನು ತೋರಿಸುತ್ತೇನೆ; ಮುಂದುವರಿಯುವ ಮೊದಲು ನೀವು ಪ್ರತಿ ಔಷಧಿಯನ್ನು ಖಚಿತಪಡಿಸಬೇಕು.",
        "te": "మీరు ప్రిస్క్రిప్షన్ పేజీలో చీటీ ఫోటో అప్‌లోడ్ చేయవచ్చు. నేను చదివి దొరికిన వివరాలు చూపిస్తాను; ముందుకు వెళ్లే ముందు మీరు ప్రతి మందును నిర్ధారించాలి.",
        "label": {"en": "Open Prescriptions", "hi": "प्रिस्क्रिप्शन खोलें", "kn": "ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್ ತೆರೆಯಿರಿ", "te": "ప్రిస్క్రిప్షన్ తెరవండి"},
        "href": "/prescriptions",
    },
    "reminder": {
        "en": "Medication reminders are created from prescriptions you have confirmed. Open the Reminders page to set the times.",
        "hi": "दवा के रिमाइंडर उन पर्चों से बनते हैं जिन्हें आपने पुष्टि किया है। समय तय करने के लिए रिमाइंडर पेज खोलें।",
        "kn": "ನೀವು ಖಚಿತಪಡಿಸಿದ ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್‌ಗಳಿಂದ ಔಷಧಿ ಜ್ಞಾಪನೆಗಳನ್ನು ರಚಿಸಲಾಗುತ್ತದೆ. ಸಮಯ ಹೊಂದಿಸಲು ರಿಮೈಂಡರ್ ಪುಟ ತೆರೆಯಿರಿ.",
        "te": "మీరు నిర్ధారించిన ప్రిస్క్రిప్షన్ల నుండి మందుల రిమైండర్లు సృష్టించబడతాయి. సమయాలు సెట్ చేయడానికి రిమైండర్ల పేజీ తెరవండి.",
        "label": {"en": "Open Reminders", "hi": "रिमाइंडर खोलें", "kn": "ರಿಮೈಂಡರ್ ತೆರೆಯಿರಿ", "te": "రిమైండర్లు తెరవండి"},
        "href": "/reminders",
    },
    "greeting": {
        "en": "Namaste! I'm Swasthya Mitra. Ask me a health question by typing or speaking. I give general information, not a diagnosis.",
        "hi": "नमस्ते! मैं स्वास्थ्य मित्र हूँ। टाइप करके या बोलकर स्वास्थ्य से जुड़ा सवाल पूछें। मैं सामान्य जानकारी देता हूँ, निदान नहीं।",
        "kn": "ನಮಸ್ಕಾರ! ನಾನು ಸ್ವಾಸ್ಥ್ಯ ಮಿತ್ರ. ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಮಾತನಾಡಿ ಆರೋಗ್ಯ ಪ್ರಶ್ನೆ ಕೇಳಿ. ನಾನು ಸಾಮಾನ್ಯ ಮಾಹಿತಿ ಕೊಡುತ್ತೇನೆ, ರೋಗನಿರ್ಣಯ ಅಲ್ಲ.",
        "te": "నమస్తే! నేను స్వాస్థ్య మిత్రను. టైప్ చేసి లేదా మాట్లాడి ఆరోగ్య ప్రశ్న అడగండి. నేను సాధారణ సమాచారం ఇస్తాను, వ్యాధి నిర్ధారణ కాదు.",
    },
}
_INTENT_PATTERNS = {
    "prescription": re.compile(r"prescription|read (my )?(medicine|prescription)|scan (my )?(medicine|prescription)|प्रिस्क्रिप्शन|पर्चा|पर्ची|ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್|ಚೀಟಿ|ప్రిస్క్రిప్షన్|చీటీ", re.I),
    "reminder": re.compile(r"remind(er)?s?\b|alarm|रिमाइंडर|याद दिला|ರಿಮೈಂಡರ್|ಜ್ಞಾಪನ|రిమైండర్|గుర్తు చేయ", re.I),
    "greeting": re.compile(r"^\s*(hi|hello|hey|namaste|namaskara|namaskar|नमस्ते|ನಮಸ್ಕಾರ|నమస్తే)\W*$", re.I),
}

LLM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "urgency": {"type": "STRING", "enum": ["none", "urgent", "emergency"]},
        "cited": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        "topic": {"type": "STRING", "enum": ["health", "general", "emotional", "activity"]},
    },
    "required": ["answer", "urgency"],
}

# The system prompt (persona + general help + health safety rules) lives in services/companion.py and is used for one Gemini call.

GENERAL_UNAVAILABLE = {
    "en": "I'm unable to connect to my AI service right now. Please try again in a little while.",
    "hi": "अभी मैं अपनी AI सेवा से जुड़ नहीं पा रहा हूँ। कृपया थोड़ी देर बाद फिर कोशिश करें।",
    "kn": "ಈಗ ನನ್ನ AI ಸೇವೆಗೆ ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    "te": "ప్రస్తుతం నా AI సేవకు కనెక్ట్ కాలేకపోతున్నాను. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి.",
}
# ---------------------------------------------------------------------------------------------
def _contacts(db: Session, user: User) -> list[dict]:
    from sqlalchemy import select

    rows = db.scalars(
        select(EmergencyContact).where(EmergencyContact.user_id == user.id).order_by(EmergencyContact.is_primary.desc())
    )
    return [{"id": c.id, "name": c.name, "phone": c.phone, "relationship": c.relationship_, "is_primary": c.is_primary} for c in rows]


_HEALTH_EN = re.compile(
    r"\b(health|medical|doctor|hospital|medicine|medication|tablet|pill|dose|dosage|"
    r"prescription|symptom|pain|fever|cough|cold|headache|dizziness|vomit|vomiting|"
    r"diarrhea|diarrhoea|blood pressure|diabetes|sugar level|heart|chest|breathing|"
    r"pregnan\w*|injury|wound|infection|allergy|allergic|rash|swelling|stroke|seizure|"
    r"insulin|antibiotic|depression|anxiety|mental health|suicid\w*|self harm)\b",
    re.I,
)

_HEALTH_LOCAL = (
    "दवा", "दवाई", "डॉक्टर", "अस्पताल", "बुखार", "दर्द", "खांसी", "जुकाम",
    "ಸಿರದ", "ಔಷಧಿ", "ಮದ್ದು", "ವೈದ್ಯರು", "ಆಸ್ಪತ್ರೆ", "ಜ್ವರ", "ನೋವು", "ಕೆಮ್ಮು",
    "ಮಧುಮೇಹ", "ರಕ್ತದೊತ್ತಡ",
    "మందు", "మందులు", "డాక్టర్", "ఆసుపత్రి", "జ్వరం", "నొప్పి", "దగ్గు",
    "మధుమేహం", "రక్తపోటు",
)

def _is_health_query(text: str) -> bool:
    if _HEALTH_EN.search(text):
        return True
    lowered = text.lower()
    return any(term in lowered for term in _HEALTH_LOCAL)


def _route_intent(text: str) -> str:
    words = text.split()

    for name in ("greeting", "prescription", "reminder"):
        if _INTENT_PATTERNS[name].search(text):
            if name == "greeting" and len(words) <= 3:
                return name
            if name != "greeting" and len(words) <= 12:
                return name

    return "health_query" if _is_health_query(text) else "general_query"
def _history_for_llm(db: Session, session: ChatSession | None, payload: ChatIn) -> list[dict]:
    turns: list[tuple[str, str]] = []
    if session is not None:
        from sqlalchemy import select

        rows = db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.desc()).limit(6)
        ).all()
        turns = [(m.role, m.content) for m in reversed(rows)]
    else:
        turns = [(h.role, h.content) for h in payload.history[-6:]]
    return [{"role": "user" if r == "user" else "model", "parts": [{"text": c}]} for r, c in turns]


def handle_message(db: Session, user: User, payload: ChatIn, session: ChatSession | None) -> tuple[ChatOut, ChatSession | None]:
    consents = current_consents(db, user.id)
    text = payload.message.strip()
    lang = payload.language or detect_language(text, user.preferred_language)
    detected = detect_language(text, lang)
    if detected != "en" or payload.language is None:
        lang = detected  # the language the user actually wrote in wins over the UI hint
    disclaimer = DISCLAIMER[lang]

    # 2 ── safety check: deterministic and before any LLM call ──────────────────────────────────
    sres = safety.assess(text)
    if sres.is_emergency:
        db.add(EmergencyEvent(user_id=user.id, trigger="red_flag", severity="emergency", flags=sres.flags))
        db.commit()
        out = ChatOut(
            session_id=session.id if session else None,
            reply=safety.emergency_message(sres, lang), language=lang, mode="emergency", disclaimer=disclaimer, stored=False,
            safety=SafetyOut(level="emergency", flags=sres.flags, labels=sres.labels, numbers=safety.numbers_for(sres), contacts=_contacts(db, user)),
        )
        return out, session

    safety_out = SafetyOut(level=sres.level, flags=sres.flags, labels=sres.labels)
    if sres.level == "urgent":
        safety_out.banner = safety.urgent_message(lang)

    # 3 ── intent routing + companion small talk ─────────────────────────────────────────────────
    intent = _route_intent(text)
    ai_ok = consents["ai_processing"] and get_gemini().configured
    first_name = (user.full_name or "").split()[0] if user.full_name else None
    period = companion.local_period(user.timezone)
    first_turn = session is None and not payload.history
    small_talk = companion.detect(text) if sres.level == "none" else None

    def _companion_out(reply_text: str, topic: str) -> ChatOut:
        return ChatOut(session_id=session.id if session else None, reply=reply_text, language=lang, mode="companion", topic=topic,
                       safety=safety_out, disclaimer=disclaimer, stored=False)

    if sres.level == "none" and intent == "greeting":  # time-aware, works with or without AI
        return _companion_out(companion.greeting(lang, period, first_name), "emotional"), session
    if small_talk == "goodbye":  # gentle closing only when the user is clearly leaving
        return _companion_out(companion.CLOSING[lang], "emotional"), session
    if small_talk in ("lonely", "relax", "game") and not ai_ok:
        # Without the AI service we only offer short, safe, scripted support – never invented content.
        return _companion_out(companion.FALLBACK[small_talk][lang], companion.TOPIC[small_talk]), session
    if intent in NAV and intent != "greeting" and sres.level == "none":
        entry = NAV[intent]
        actions = [{"label": entry["label"][lang], "href": entry["href"]}] if "label" in entry else []
        return ChatOut(
            session_id=session.id if session else None, reply=entry[lang], language=lang, mode="navigation",
            safety=safety_out, actions=actions, disclaimer=disclaimer, stored=False,
        ), session

    # Non-health question and no AI available: be honest instead of showing an unrelated health note.
    if intent == "general_query" and not ai_ok:
        return ChatOut(
            session_id=session.id if session else None, reply=GENERAL_UNAVAILABLE[lang], language=lang, mode="unavailable",
            unavailable_reason="no_consent" if not consents["ai_processing"] else "not_configured",
            safety=safety_out, disclaimer=disclaimer, stored=False, topic="general",
        ), session

    # 4 ── retrieval (always: cheap, and lets the model notice when a question is really about health) ──
    passages = rag.retrieve(db, text, k=4, use_embeddings=consents["ai_processing"])
    sources = [Source(n=i + 1, title=p.title, section=p.section, source_name=p.source_name, source_url=p.source_url, review_status=p.review_status) for i, p in enumerate(passages)]

    # 5 ── personalisation (consent-gated) ─────────────────────────────────────────────────────
    ctx_text, meds_text = ("", "")
    if consents["health_data_personalisation"]:
        ctx_text, meds_text = personalisation.build_context(db, user)

    reply, mode, reason, guard_removed, topic = "", "retrieval_only", None, [], None
    if not ai_ok:
        reason = "no_consent" if not consents["ai_processing"] else "not_configured"
    else:
        # 6 ── ONE Gemini call: persona + general help + health rules ──────────────────────────────
        src_block = "\n\n".join(f"[{i+1}] {p.title} – {p.section}: {p.text}" for i, p in enumerate(passages)) or "(no relevant sources found)"
        user_block = f"SOURCES:\n{src_block}\n\n"
        if ctx_text:
            user_block += f"USER CONTEXT (private, use only to personalise):\n{ctx_text}\n\n"
        user_block += f"QUESTION:\n{text}"
        contents = _history_for_llm(db, session, payload) + [{"role": "user", "parts": [{"text": user_block}]}]
        try:
            data = get_gemini().generate_json(
                system=companion.persona_prompt(LANGUAGE_NAMES[lang], first_name, period, lang, first_turn), contents=contents, json_schema=LLM_SCHEMA,
            )
            answer = str(data.get("answer", "")).strip()
            # 7 ── the LLM may only raise urgency, never lower what rules found ─────────────────
            llm_level = data.get("urgency", "none")
            if llm_level in ("urgent", "emergency"):
                sres = safety.escalate(sres, llm_level)
            if sres.is_emergency:
                db.add(EmergencyEvent(user_id=user.id, trigger="llm_urgency", severity="emergency", flags=sres.flags))
                db.commit()
                out = ChatOut(
                    session_id=session.id if session else None, reply=safety.emergency_message(sres, lang), language=lang,
                    mode="emergency", disclaimer=disclaimer, stored=False,
                    safety=SafetyOut(level="emergency", flags=sres.flags, labels=sres.labels, numbers=safety.numbers_for(sres), contacts=_contacts(db, user)),
                )
                return out, session
            if sres.level == "urgent":
                safety_out = SafetyOut(level="urgent", flags=sres.flags, labels=sres.labels, banner=safety.urgent_message(lang))
            # The model can never talk a health question out of the strict rules: keyword/urgency evidence wins.
            topic = data.get("topic") if data.get("topic") in ("health", "general", "emotional", "activity") else "health"
            if intent == "health_query" or sres.level == "urgent":
                topic = "health"
            # 8 ── output guard (strict for health, medicine-only for everyday topics) ───────────
            if topic == "health":
                allowed = "\n".join(p.text for p in passages) + "\n" + meds_text
                answer, guard_removed = guard.strip_unsupported_claims(answer, allowed)
            else:
                answer, guard_removed = companion.guard_general(answer)
            if topic == "health":
                if answer:
                    reply, mode = answer, "llm_rag"
                    cited = {c for c in data.get("cited", []) if isinstance(c, int)}
                    if cited:
                        sources = [s for s in sources if s.n in cited] or sources
                else:
                    reply, mode = NO_INFO[lang], "llm_rag"
            else:
                sources = []  # library notes are only shown for health answers
                if answer:
                    reply, mode = answer, "general_chat"
                else:
                    reply, mode, reason = GENERAL_UNAVAILABLE[lang], "unavailable", "error"
        except GeminiError as exc:
            log.warning("LLM unavailable for chat: %s", exc)
            reason = "error"

    if not reply:  # graceful degradation: no LLM available
        if intent == "general_query":
            reply, mode, sources = GENERAL_UNAVAILABLE[lang], "unavailable", []
        elif lang == "en" and passages:
            top = passages[0]
            reply = f"From my trusted notes on “{top.title}” – {top.section}:\n\n{top.text}"
            sources = sources[:1]
            mode = "retrieval_only"
        else:
            reply, mode, sources = UNAVAILABLE[lang], "unavailable", []

    out = ChatOut(
        session_id=session.id if session else None, reply=reply, language=lang, mode=mode, unavailable_reason=reason if mode in ("unavailable", "retrieval_only") else None,
        safety=safety_out, sources=sources, disclaimer=disclaimer, stored=False, guard_removed=guard_removed, topic=topic,
    )
    return out, session


def persist_turn(db: Session, user: User, session: ChatSession | None, user_text: str, out: ChatOut) -> ChatSession:
    """Store the exchange (encrypted columns) – callers only invoke this with store_chat_history consent."""
    if session is None:
        session = ChatSession(user_id=user.id, title=user_text[:60])
        db.add(session)
        db.flush()
    level = out.safety.level
    # Explicit timestamps: on Windows the clock is coarse, so two rows could tie and then sort in random id order.
    now = utcnow()
    db.add(ChatMessage(session_id=session.id, user_id=user.id, role="user", content=user_text, language=out.language, safety_level=level, created_at=now))
    db.add(ChatMessage(
        session_id=session.id, user_id=user.id, role="assistant", created_at=now + timedelta(milliseconds=5), content=out.reply, language=out.language, intent=out.mode,
        safety_level=level, sources=[s.model_dump() for s in out.sources],
    ))
    db.commit()
    out.session_id, out.stored = session.id, True
    return session
