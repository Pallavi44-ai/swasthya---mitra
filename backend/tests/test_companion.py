"""Ask Mitra companion: personality, time-aware greeting, emotional support, games, safety precedence, consent."""
import json
from datetime import datetime, timezone

from app.models import ChatMessage
from app.db.session import SessionLocal
from app.services import companion
from tests.conftest import register
from tests.helpers import gemini_text_response, install_fake_gemini


def _llm(answer="Hello.", topic="general", urgency="none", cited=None, seen=None):
    def handler(req):
        if seen is not None:
            seen.append(json.loads(req.content))
        return gemini_text_response({"answer": answer, "urgency": urgency, "cited": cited or [], "topic": topic})
    return handler


def _system(seen):
    return seen[-1]["systemInstruction"]["parts"][0]["text"]


# ---- greeting -------------------------------------------------------------------------------------------
def test_local_period_uses_users_timezone():
    t = datetime(2026, 11, 7, 4, 30, tzinfo=timezone.utc)  # 10:00 in India, 04:30 in London
    assert companion.local_period("Asia/Kolkata", t) == "morning"
    assert companion.local_period("Europe/London", t) == "night"
    assert companion.local_period("Nowhere/Invalid", t) == "morning"  # falls back to India time
    assert companion.local_period("Asia/Kolkata", datetime(2026, 1, 1, 7, 30, tzinfo=timezone.utc)) == "afternoon"  # 13:00


def test_greeting_is_time_aware_named_and_works_without_ai(client, monkeypatch):
    register(client, name="Asha Rao")
    monkeypatch.setattr(companion, "local_period", lambda tz, now=None: "evening")
    r = client.post("/api/chat", json={"message": "hello"}).json()
    assert r["mode"] == "companion" and r["reply"].startswith("Good evening, Asha!")
    assert "how are you feeling" in r["reply"].lower()
    h = client.post("/api/chat", json={"message": "नमस्ते", "language": "hi"}).json()
    assert h["language"] == "hi" and h["reply"].startswith("शुभ संध्या, Asha!")


# ---- emotional support ----------------------------------------------------------------------------------
def test_loneliness_without_ai_is_empathetic_and_does_not_claim_to_replace_family(client):
    register(client)
    r = client.post("/api/chat", json={"message": "I feel lonely today"}).json()
    assert r["mode"] == "companion" and r["topic"] == "emotional" and r["safety"]["level"] == "none"
    low = r["reply"].lower()
    assert "natural" in low and "happy memory" in low and "cannot replace" in low
    assert "should not feel" not in low and "don't be sad" not in low
    assert r["sources"] == []


def test_loneliness_in_all_four_languages_without_ai(client):
    register(client)
    for lang, msg in [("hi", "मैं बहुत अकेला महसूस करता हूँ"), ("kn", "ನನಗೆ ತುಂಬಾ ಒಂಟಿ ಅನಿಸುತ್ತಿದೆ"), ("te", "నాకు చాలా ఒంటరిగా ఉంది")]:
        r = client.post("/api/chat", json={"message": msg}).json()
        assert r["mode"] == "companion" and r["language"] == lang and r["reply"] == companion.LONELY[lang]


def test_relax_and_game_without_ai_are_honest(client):
    register(client)
    relax = client.post("/api/chat", json={"message": "Help me relax"}).json()
    assert relax["mode"] == "companion" and "breathe" in relax["reply"].lower() and "dizzy" in relax["reply"].lower()
    game = client.post("/api/chat", json={"message": "Let's play a game"}).json()
    assert game["mode"] == "companion" and "not available right now" in game["reply"]  # no pretending to play


def test_health_questions_are_not_hijacked_by_small_talk_rules(client):
    register(client)
    for q in ["Does stress raise blood pressure?", "I am feeling low sugar today, what to eat?", "How do I make ORS at home?"]:
        assert client.post("/api/chat", json={"message": q}).json()["mode"] != "companion", q


# ---- with Gemini: the SAME service, persona in the system prompt -----------------------------------------
def test_ai_path_uses_persona_name_language_and_plain_text_rules(client):
    register(client, name="Asha Rao")
    seen = []
    install_fake_gemini(_llm("I am sorry you feel this way, Asha.", topic="emotional", seen=seen))
    r = client.post("/api/chat", json={"message": "I miss my children so much", "language": "en"}).json()
    sp = _system(seen)
    assert r["mode"] == "general_chat" and r["topic"] == "emotional" and r["sources"] == []
    assert "first name is Asha" in sp and "English only" in sp and "Plain text only" in sp
    assert "START of a new conversation" in sp and "Good" in sp


def test_second_turn_does_not_greet_again(client):
    register(client)
    seen = []
    install_fake_gemini(_llm(seen=seen))
    client.post("/api/chat", json={"message": "Tell me about the Taj Mahal", "history": [
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": "Good morning!"}]})
    assert "do not greet again" in _system(seen) and "START of a new conversation" not in _system(seen)


def test_general_question_is_answered_without_library_sources_and_in_each_language(client):
    register(client)
    for lang, name in [("en", "English"), ("hi", "Hindi"), ("kn", "Kannada"), ("te", "Telugu")]:
        seen = []
        install_fake_gemini(_llm("Answer.", topic="general", cited=[1], seen=seen))
        r = client.post("/api/chat", json={"message": "Who built the Taj Mahal?", "language": lang}).json()
        assert r["mode"] == "general_chat" and r["topic"] == "general" and r["sources"] == []
        assert f"Reply in {name} only" in _system(seen)


def test_health_answers_keep_sources_and_the_medical_rules(client):
    register(client)
    seen = []
    install_fake_gemini(_llm("Drink ORS in small sips [1].", topic="health", cited=[1], seen=seen))
    r = client.post("/api/chat", json={"message": "I have loose motions, what should I do?"}).json()
    sp = _system(seen)
    assert r["topic"] == "health" and r["sources"]
    for rule in ("Never diagnose", "NEVER state or suggest medicine names", "NEVER tell the user to start, stop"):
        assert rule in sp


def test_output_guard_still_strips_invented_doses_in_companion_answers(client):
    register(client)
    install_fake_gemini(_llm("Take 500 mg of paracetamol three times a day.", topic="health"))
    r = client.post("/api/chat", json={"message": "what can I take for body ache?"}).json()
    assert "500 mg" not in r["reply"] and r["guard_removed"]


# ---- safety always wins ---------------------------------------------------------------------------------
def test_emergency_beats_companion_and_games(client):
    register(client)
    for msg in ["I feel lonely and I have severe chest pain", "let's play a game, I cannot breathe", "I want to end my life, I feel so alone"]:
        install_fake_gemini(_llm("Let's play!"))
        r = client.post("/api/chat", json={"message": msg}).json()
        assert r["mode"] == "emergency" and any(n["number"] == "108" or n["number"] for n in r["safety"]["numbers"]), msg


def test_llm_can_still_raise_urgency_from_a_companion_chat(client):
    register(client)
    install_fake_gemini(_llm("Please call 108 now.", topic="health", urgency="emergency"))
    assert client.post("/api/chat", json={"message": "my father seems very confused and drowsy"}).json()["mode"] == "emergency"


# ---- closing + consent ----------------------------------------------------------------------------------
def test_goodbye_gets_gentle_closing_but_thanks_alone_does_not(client):
    register(client)
    r = client.post("/api/chat", json={"message": "ok bye"}).json()
    assert r["mode"] == "companion" and r["reply"] == companion.CLOSING["en"]
    assert client.post("/api/chat", json={"message": "thank you"}).json()["reply"] != companion.CLOSING["en"]


def test_emotional_chats_are_not_stored_without_consent(client):
    register(client, consents={"store_chat_history": False})
    r = client.post("/api/chat", json={"message": "I feel lonely today"}).json()
    assert r["stored"] is False and r["session_id"] is None
    with SessionLocal() as db:
        assert db.query(ChatMessage).count() == 0


def test_emotional_chats_are_stored_when_user_consented(client):
    register(client, consents={"store_chat_history": True})
    r = client.post("/api/chat", json={"message": "I feel lonely today"}).json()
    assert r["stored"] is True
    with SessionLocal() as db:
        assert db.query(ChatMessage).count() == 2


def test_no_invented_personal_details_in_fallback_replies():
    for lang in companion.LANGS:
        for text in (companion.LONELY[lang], companion.RELAX[lang], companion.GAME_NEEDS_AI[lang], companion.CLOSING[lang]):
            assert "your son" not in text.lower() and "your wife" not in text.lower() and "your daughter" not in text.lower()
