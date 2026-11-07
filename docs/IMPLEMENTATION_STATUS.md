# Implementation status (honest)

Legend: ✅ implemented **and tested** · 🟡 implemented, only partly verified · ⚙️ needs your configuration · ❌ not built

## Fully implemented and tested
| Area | Evidence |
|---|---|
| Registration with code confirmation, login = password + OTP, logout (server-side revoke), forgot/reset password, change password | 34 MFA tests + browser E2E |
| OTP expiry, 5-attempt lockout, resend cooldown/cap, single use, purpose binding, hashed storage, no enumeration | pytest (`tests/test_mfa.py`) |
| Device sessions list/revoke, sign out all, idle timeout, forged cookie rejected | pytest |
| Per-user data isolation (profile, records, prescriptions, reminders, chat), 401 on all protected routes | pytest + E2E |
| Consent ledger enforced server-side (5 purposes, default off) | pytest + E2E |
| Rule-based red-flag/emergency detection (EN/HI/KN/TE) before any LLM; self-harm routing | pytest (incl. mutation check) + E2E |
| Prescription pipeline: quality check, real Tesseract OCR, rule parser, review/edit, confirmation gate | pytest + E2E with a synthetic prescription image |
| Reminders from confirmed items only, dose log, missed after 3 h, adherence, in-app alert while app is open | pytest + E2E |
| Emergency screen (108, contacts, prepared message), health profile, records, timeline, data export, account deletion | pytest + E2E |
| Field-level encryption at rest | pytest (ciphertext inspected in DB) |
| SQLite and PostgreSQL 16 | all 106 tests pass on both |
| Responsive layout, large text, high contrast, 4-language core UI | E2E screenshots (mobile 390 px, no horizontal scroll); small-target check on sign-in pages |

## Implemented but only partly verified
* **Biometric sign-in (passkeys)** – works end-to-end in headless Chromium using a *virtual authenticator*. Not tried with a real fingerprint reader/phone, Safari or Firefox.
* **SMTP delivery** – tested against a local SMTP server, not a real provider.
* **Voice (browser Web Speech)** – code present; speech recognition/synthesis quality cannot be verified in headless tests and varies by device (Kannada/Telugu especially).
* **Translations / Kannada-Telugu-Hindi phrase lists** – core UI strings and red-flag phrases exist; **need review by native speakers and clinicians.**
* **RAG knowledge base** – 13 *starter* documents marked "starter-unreviewed"; need clinical review before real use.
* **Forgot-password page** – one combined page (email → code + new password). `/reset-password` just redirects to it.

## Needs your configuration (not verified live from here)
* ⚙️ **Gemini** (`GEMINI_API_KEY`): chat answers, LLM prescription extraction, transcription, embeddings. The client was tested only against a **mocked** HTTP transport; the sandbox had no access to Google. Until a key is added the app says so on the Status page and falls back to retrieval-only answers.
* ⚙️ **Twilio SMS** – request format tested with a mock only; Indian DLT registration is your responsibility.
* ⚙️ **SMTP account** for real email codes (mandatory in production).
* ⚙️ **Tesseract language packs** for Hindi/Kannada/Telugu OCR (only English OCR was tested).
* ⚙️ **HTTPS + domain** for passkeys and secure cookies in production.

## Not implemented / known limitations
* ❌ Background push notifications – reminders alert only while the app is open.
* ❌ Appointment booking, doctor/admin roles, EHR integration (outside the approved scope).
* ❌ Database migrations (Alembic) – dev DB must be recreated if models change.
* ❌ Shared rate limiter – in-memory, single process.
* ❌ Not tested on Windows itself, with a screen reader, with elderly users, or under load. No clinical validation; not a medical device.
