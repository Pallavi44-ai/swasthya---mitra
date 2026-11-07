# Architecture (maps to the approved Phase-I/Review-3 design)

```
Browser (Next.js, Web Speech API)            ──same-origin /api proxy──▶  FastAPI
  pages: auth, dashboard, chat, prescriptions,                          ├─ api/routes   thin HTTP layer + auth dependency
  reminders, profile, records, emergency,                               ├─ services     business logic (below)
  privacy, security, status                                             ├─ models       SQLAlchemy tables (field-level Fernet encryption)
                                                                        └─ SQLite (default) or PostgreSQL
External (optional): Google Gemini REST · SMTP server · Twilio SMS · Tesseract (local binary)
```

| Report module | Where it lives | Notes |
|---|---|---|
| Voice interface (STT/TTS, multilingual) | `frontend/lib/speech.ts`, `routes/voice.py`, `services/gemini.py` | Browser Web Speech first; server transcription via Gemini if configured |
| Multimodal LLM assistant | `services/chat_service.py`, `gemini.py`, `guard.py` | Gemini only after consent; output guard strips invented doses |
| RAG over curated knowledge | `services/rag.py`, 13 starter documents | BM25 + optional embeddings; relevance floor; sources shown |
| Prescription reading | `services/ocr.py`, `prescription_parser.py`, `prescription_service.py` | Quality check → Tesseract → Gemini/rule parse → **user confirmation gate** |
| Medication reminders & adherence | `services/reminders.py` | Only from *confirmed* items (enforced by DB FK + service) |
| Emergency / red-flag detection | `services/safety.py`, `data/red_flags.json`, `routes/emergency.py` | Deterministic, runs before any LLM; LLM may only raise urgency |
| Personalisation | `services/personalisation.py` | Only with consent `health_data_personalisation` |
| Privacy & consent | `services/consent.py`, `models/user.py` | 5 purposes, enforced server-side; export & delete account |
| Authentication & MFA (added requirement) | `routes/auth.py`, `routes/security.py`, `services/otp*.py`, `sessions.py`, `passkeys.py` | See SECURITY_AUTH.md |

## Key flows
**Chat:** consent check → language detect → red-flag rules (emergency ⇒ stop, show 108 card) → RAG retrieve → (if consent + Gemini key) LLM with profile context → output guard → save (only if consent). Without AI: retrieval-only answer, labelled "without AI".
**Prescription:** upload → quality check → OCR → structured items with per-item confidence/flags → user edits → explicit confirm → locked → optional reminders → dose log, adherence.
**Login:** password → pending `OtpChallenge` (no cookie) → code **or** passkey → `UserSession` row + JWT cookie carrying `sid`.

Data-flow detail for the DFD figure: the Review-3 report's levels map one-to-one to the table above; no new actors were introduced (no doctor/admin roles).
