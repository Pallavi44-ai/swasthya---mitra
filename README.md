# Swasthya Mitra – AI-integrated, voice-enabled healthcare companion

Final-year B.Tech CSE capstone (CMR University). Team: Pallavi L, Pari Bhoomi, Piyush Mishra, Pragathi P N. Guide: Sheik Jamil Ahmed.

> **Not a medical device.** It does not diagnose, prescribe or change doses. Emergencies are escalated to 108 by a deterministic rule layer *before* any AI is called. No clinical validation has been done.

**What is honestly implemented, what needs configuration and what is not built: see [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).** Read it before the evaluation.

| Folder | Content |
|---|---|
| `backend/` | FastAPI + SQLAlchemy API, safety layer, RAG, OCR, reminders, authentication/MFA, **106 automated tests** |
| `frontend/` | Next.js 14 web app (4 languages, large-text and high-contrast modes, voice in/out) |
| `e2e/` | Playwright browser flow (26 steps) incl. MFA, lockout, biometric (virtual authenticator), password reset |
| `docs/` | ARCHITECTURE, API, DATABASE (+`schema.sql`), SECURITY_AUTH (+provider set-up), IMPLEMENTATION_STATUS, DEPLOYMENT |

## Run it locally on Windows (PowerShell)

Prerequisites (install once): **Python 3.11+** (python.org, tick "Add to PATH"), **Node.js 20 LTS+**, and optionally **Tesseract OCR** (UB-Mannheim Windows installer, for prescription photos).

**Window 1 – backend**
```powershell
cd swasthya-mitra\backend
python -m venv venv
# If activation is blocked:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Only if Tesseract is installed and not on PATH:
$env:Path += ";C:\Program Files\Tesseract-OCR"
uvicorn app.main:app --port 8000
```
Leave it running. In development the **login codes are printed in this window** as `DEV-ONLY OTP ... code=123456` (no email/SMS account needed). Look for that line after you press "send me a code".

**Window 2 – frontend**
```powershell
cd swasthya-mitra\frontend
npm install
npm run build
npm start
```
Open **http://localhost:3000**. (For development with hot reload use `npm run dev` instead of build/start.)

**Run the tests (Window 3, backend venv active)**
```powershell
cd swasthya-mitra\backend
python -m pytest -q
# optional PostgreSQL run:  $env:TEST_DATABASE_URL="postgresql+psycopg://postgres:PASSWORD@localhost:5432/swasthya_test"; python -m pytest -q
cd ..\frontend; npm run typecheck
```
**Browser end-to-end (optional)** – start the backend with its output saved, then:
```powershell
cd swasthya-mitra\backend; uvicorn app.main:app --port 8000 *> ..\backend.log     # Window 1 instead of the plain command
cd swasthya-mitra\e2e; npm init -y; npm i playwright; npx playwright install chromium
$env:BACKEND_LOG="..\backend.log"; node flow.js
```
> These commands were written for Windows but **only executed on Linux** (the development sandbox). Paths and activation syntax are standard, but if one step differs on your machine, see "Troubleshooting" in docs/DEPLOYMENT.md.

## Turning on the optional services
Edit `backend\.env` (see `.env.example`), restart uvicorn:
* **Gemini** (AI answers, better prescription reading, voice transcription): set `GEMINI_API_KEY`. *Not verified against the live API – see status doc.*
* **Real email codes**: `OTP_EMAIL_PROVIDER=smtp` + `SMTP_*`. **Real SMS codes**: `OTP_SMS_PROVIDER=twilio` + `TWILIO_*`. Details in docs/SECURITY_AUTH.md.
* **Hindi/Kannada/Telugu OCR**: install those Tesseract language packs and set `OCR_LANGUAGES=eng+hin+kan+tel`.
* **PostgreSQL**: set `DATABASE_URL=postgresql+psycopg://...` (tables are created automatically).

## Using the app
Register (consents are unticked by default) → confirm the emailed code → dashboard. Upload a prescription photo → check/edit what was read → tick the confirmation → *only then* create reminders. Ask health questions in the chat (voice supported by browsers that provide it). The red **Emergency** button is on every screen. **Sign-in security** (left menu) manages codes, fingerprint/face, devices and password.
