"""Test fixtures. Uses an isolated SQLite file by default; set TEST_DATABASE_URL to run on PostgreSQL."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="sm_test_")
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ.pop("GEMINI_API_KEY", None)
os.environ["GEMINI_API_KEY"] = ""  # tests never hit the network

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import rate_limiter  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import gemini  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    from app.db.session import init_db
    init_db()
    from app.services import rag
    rag.ensure_knowledge_base()
    rag._index_cache["sig"] = None
    rate_limiter.reset()
    from app.services.otp_delivery import OUTBOX
    OUTBOX.clear()
    gemini.set_gemini(None)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def register(client, email="asha@example.com", name="Asha", consents=None, language="en"):
    body = {
        "email": email, "password": "Secret123", "full_name": name, "preferred_language": language,
        "accepted_disclaimer": True,
        "consents": consents if consents is not None else {
            "ai_processing": True, "store_chat_history": True, "health_data_personalisation": True,
            "store_prescription_images": False, "emergency_sharing": True,
        },
    }
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    assert "sm_session" not in client.cookies  # no session until the code is verified
    v = client.post("/api/auth/register/verify", json={"challenge_id": r.json()["challenge_id"], "code": last_code(email)})
    assert v.status_code == 200, v.text
    return v.json()


def last_code(to, purpose=None):
    from app.services.otp_delivery import OUTBOX
    for m in reversed(OUTBOX):
        if m["to"] == to and (purpose is None or m["purpose"] == purpose):
            return m["code"]
    raise AssertionError(f"no code sent to {to}")


def login(client, email, password="Secret123"):
    """Password step, then the emailed code. Returns the final response."""
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client.post("/api/auth/mfa/verify", json={"challenge_id": r.json()["challenge_id"], "code": last_code(email, "login")})


@pytest.fixture
def user_a(client):
    register(client, "a@example.com", "A")
    return client


@pytest.fixture
def make_client():
    """Independent clients (separate cookie jars) for cross-user isolation tests."""
    clients = []

    def _make(email, consents=None):
        c = TestClient(app)
        c.__enter__()
        register(c, email, email.split("@")[0], consents)
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)
