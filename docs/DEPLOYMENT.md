# Deployment & troubleshooting

## Development (what the README does)
SQLite, console OTP (codes appear in the backend window), auto-generated dev secrets in `backend/data/.dev_secrets.json`.

## Production outline (not performed/tested by the authors)
1. PostgreSQL: create database; `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/swasthya`.
2. `backend/.env`: `APP_ENV=production`, `JWT_SECRET`, `DATA_ENCRYPTION_KEY` (back this up!), `COOKIE_SECURE=true`, `CORS_ORIGINS=https://your.site`, `OTP_EMAIL_PROVIDER=smtp` + `SMTP_*`, `WEBAUTHN_RP_ID`/`WEBAUTHN_ORIGIN`, optional Twilio and `GEMINI_API_KEY`. The API **refuses to start** if secrets or SMTP are missing.
3. Run `uvicorn app.main:app --host 127.0.0.1 --port 8000` behind a TLS reverse proxy; run the frontend with `npm run build && npm start` and set `BACKEND_URL` to the API address before building (rewrites are fixed at build time).
4. Single worker only until the rate limiter is moved to a shared store; add Alembic migrations before the first schema change.
5. Install Tesseract and language packs on the server.

## Troubleshooting (Windows)
* `Activate.ps1 cannot be loaded` → `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
* `tesseract is not installed` on photo upload → install it and add `C:\Program Files\Tesseract-OCR` to PATH, restart uvicorn.
* No code arrives in development → the code is in the **uvicorn window** (`DEV-ONLY OTP`). With real SMTP, check spam.
* Login page says session expired → idle timeout (60 min) or password reset signed you out.
* `Cannot reach the server` → backend not running on port 8000 (or `BACKEND_URL` differs).
* Database error after updating the code → delete `backend\data\swasthya.db` (dev only) so tables are recreated.
