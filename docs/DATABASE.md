# Database

* Engine: SQLite by default (`backend/data/swasthya.db`), PostgreSQL via `DATABASE_URL`. Tests pass on both (SQLite and PostgreSQL 16).
* Tables are created automatically at start-up (`create_all`). **There are no migrations (no Alembic).** After pulling a version that changes columns, delete the dev SQLite file (or drop the tables) – this is a development limitation; add Alembic before real deployment.
* Full DDL: [schema.sql](schema.sql) (PostgreSQL dialect, 17 tables).

| Table | Purpose |
|---|---|
| users | account, bcrypt hash, verified flags, MFA channel, `token_version` |
| otp_challenges | pending verification step: **HMAC of the code**, expiry, attempts, sends |
| user_sessions | logged-in devices (revocable, idle timeout) |
| webauthn_credentials | passkey public keys + sign counters (no biometric data) |
| consent_records | append-only consent ledger (5 purposes) |
| health_profiles, health_records, emergency_contacts | personal health data (sensitive fields encrypted) |
| prescriptions, prescription_items | OCR/LLM extraction, user-confirmed values, status |
| reminders, dose_logs | schedules from confirmed items; taken/missed/skipped |
| chat_sessions, chat_messages | optional saved conversations (consent) |
| emergency_events | when emergency guidance was shown |
| knowledge_chunks | RAG corpus (+ optional embeddings) |
| audit_logs | login/security events (no health content) |

Encrypted columns (`EncryptedText`/`EncryptedJSON`) store Fernet ciphertext. Losing `DATA_ENCRYPTION_KEY` makes them unreadable.
