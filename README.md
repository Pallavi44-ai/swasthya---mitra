# Swasthya Mitra – AI-Integrated, Voice-Enabled Healthcare Companion

Final-year B.Tech CSE capstone project at CMR University.

**Team:** Pallavi L, Pari Bhoomi, Piyush Mishra, Pragathi P N  
**Guide:** Sheik Jamil Ahmed

> **Important:** This project is not a medical device. It does not diagnose, prescribe, or change medication doses. Emergencies are escalated to 108 through a deterministic rule layer before AI is called. The system has not undergone clinical validation.

For an honest breakdown of implemented features, configuration requirements, and pending work, see [Implementation Status](docs/IMPLEMENTATION_STATUS.md).

## Project Structure

| Folder | Contents |
|---|---|
| `backend/` | FastAPI backend, authentication, safety layer, RAG, OCR, reminders and tests |
| `frontend/` | Next.js 14 web application with multilingual and voice features |
| `e2e/` | Browser end-to-end test flow |
| `docs/` | Architecture, API, database, security, deployment and implementation documentation |

## Prerequisites

- Python 3.11+
- Node.js 20 LTS+
- Tesseract OCR (optional, for prescription image processing)

## Run Locally on Windows

### 1. Backend

Open PowerShell:

```powershell
cd backend
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --port 8000
```

Configure your local `backend/.env` before enabling external services.

### 2. Frontend

Open another PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### 3. Run Backend Tests

With the backend virtual environment activated:

```powershell
cd backend
python -m pytest -q
```

### 4. Frontend Type Check

```powershell
cd frontend
npm run typecheck
```

## Optional Services

The following services require configuration:

- **Gemini AI:** Configure `GEMINI_API_KEY`.
- **Email OTP:** Configure SMTP credentials.
- **SMS OTP:** Configure Twilio credentials.
- **Regional-language OCR:** Install the required Tesseract language packs.
- **PostgreSQL:** Configure the database connection.

Never upload actual credentials or private `.env` files to GitHub. Use the `.env.example` templates.

## Using the Application

Register an account, provide the required consent, and explore the available features:

- Ask Mitra healthcare chatbot
- Prescription upload and analysis
- Medication reminders
- Emergency assistance
- User profile and health records
- Security and authentication settings

**Project status:** This is an ongoing academic project. Some features may require configuration or further development. Refer to `docs/IMPLEMENTATION_STATUS.md` before evaluating the application.