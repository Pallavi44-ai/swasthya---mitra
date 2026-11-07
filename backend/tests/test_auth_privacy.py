"""Authentication, authorisation (user-specific data), consent, encryption-at-rest, export & deletion."""
from sqlalchemy import text

from app.db.session import engine
from tests.conftest import login, register


def test_register_login_me_logout(client):
    register(client, "x@example.com", "Xavier")
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == "x@example.com" and me["consents"]["ai_processing"] is True
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, "x@example.com").status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_protected_routes_need_auth(client):
    for path in ["/api/profile", "/api/records", "/api/contacts", "/api/prescriptions", "/api/reminders/today", "/api/chat/sessions", "/api/emergency", "/api/timeline", "/api/account/export"]:
        assert client.get(path).status_code == 401, path


def test_registration_validation(client):
    base = {"email": "v@example.com", "password": "Secret123", "full_name": "V", "accepted_disclaimer": True}
    assert client.post("/api/auth/register", json={**base, "accepted_disclaimer": False}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "short1"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "allletters"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "consents": {"bogus": True}}).status_code == 422
    r = client.post("/api/auth/register", json=base)
    assert r.status_code == 201
    from tests.conftest import last_code
    client.post("/api/auth/register/verify", json={"challenge_id": r.json()["challenge_id"], "code": last_code("v@example.com")})
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json=base).status_code == 409  # duplicate of a verified account


def test_wrong_password_and_rate_limit(client):
    register(client, "r@example.com")
    client.post("/api/auth/logout")
    for _ in range(8):
        assert client.post("/api/auth/login", json={"email": "r@example.com", "password": "Wrong1234"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "r@example.com", "password": "Secret123"}).status_code == 429


def test_consents_default_to_off_unless_ticked(client):
    register(client, "c@example.com", consents={})
    assert not any(client.get("/api/consents").json()["consents"].values())
    r = client.put("/api/consents", json={"consents": {"store_chat_history": True}})
    assert r.json()["consents"]["store_chat_history"] is True
    assert client.put("/api/consents", json={"consents": {"nope": True}}).status_code == 422


def test_user_data_isolation(make_client):
    a, b = make_client("a@example.com"), make_client("b@example.com")
    rec = a.post("/api/records", json={"record_type": "visit", "title": "Check-up", "record_date": "2026-01-05", "details": "BP fine"}).json()
    contact = a.post("/api/contacts", json={"name": "Son", "phone": "+919876543210"}).json()
    assert b.get("/api/records").json() == []
    assert b.get("/api/contacts").json() == []
    for method, url in [("put", f"/api/records/{rec['id']}"), ("delete", f"/api/records/{rec['id']}"), ("delete", f"/api/contacts/{contact['id']}")]:
        kwargs = {"json": {"record_type": "visit", "title": "x", "record_date": "2026-01-05"}} if method == "put" else {}
        assert getattr(b, method)(url, **kwargs).status_code == 404
    assert len(a.get("/api/records").json()) == 1  # untouched


def test_sensitive_fields_are_encrypted_at_rest(user_a):
    secret = "Hypertension diagnosed 2019 – secret-marker-123"
    user_a.post("/api/records", json={"record_type": "condition", "title": "BP", "record_date": "2026-01-05", "details": secret})
    user_a.put("/api/profile", json={"allergies": ["Penicillin-marker"], "notes": "private-note-marker"})
    with engine.connect() as c:
        raw = " ".join(str(v) for row in c.execute(text("SELECT details FROM health_records")) for v in row)
        raw += " ".join(str(v) for row in c.execute(text("SELECT allergies, notes FROM health_profiles")) for v in row)
    assert "secret-marker" not in raw and "Penicillin-marker" not in raw and "private-note-marker" not in raw
    assert user_a.get("/api/records").json()[0]["details"] == secret  # but decrypts transparently
    assert user_a.get("/api/profile").json()["allergies"] == ["Penicillin-marker"]


def test_profile_and_contacts_validation(user_a):
    assert user_a.put("/api/profile", json={"blood_group": "Z+"}).status_code == 422
    assert user_a.put("/api/profile", json={"height_cm": 5}).status_code == 422
    assert user_a.put("/api/profile", json={"date_of_birth": "2999-01-01"}).status_code == 422
    r = user_a.put("/api/profile", json={"date_of_birth": "1950-05-01", "allergies": ["Dust", "dust", " "]}).json()
    assert r["allergies"] == ["Dust"] and r["age"] >= 76
    assert user_a.post("/api/contacts", json={"name": "X", "phone": "abc"}).status_code == 422
    first = user_a.post("/api/contacts", json={"name": "Son", "phone": "98765 43210"}).json()
    assert first["is_primary"] is True and first["phone"] == "9876543210"
    second = user_a.post("/api/contacts", json={"name": "Daughter", "phone": "9123456780", "is_primary": True}).json()
    prim = [c for c in user_a.get("/api/contacts").json() if c["is_primary"]]
    assert len(prim) == 1 and prim[0]["id"] == second["id"]
    assert user_a.post("/api/records", json={"record_type": "visit", "title": "t", "record_date": "2999-01-01"}).status_code == 422


def test_export_and_account_deletion(make_client):
    a = make_client("del@example.com")
    a.post("/api/records", json={"record_type": "note", "title": "n", "record_date": "2026-01-01"})
    exp = a.get("/api/account/export").json()
    assert exp["user"]["email"] == "del@example.com" and len(exp["records"]) == 1
    assert a.post("/api/account/delete", json={"password": "nope12345"}).status_code == 400
    assert a.post("/api/account/delete", json={"password": "Secret123"}).status_code == 204
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM health_records")).scalar() == 0
        assert c.execute(text("SELECT count(*) FROM users")).scalar() == 0
        assert c.execute(text("SELECT count(*) FROM consent_records")).scalar() == 0


def test_logout_all_invalidates_sessions(user_a):
    user_a.post("/api/auth/logout-all")
    assert user_a.get("/api/auth/me").status_code == 401


def test_timeline_merges_sources(user_a):
    user_a.post("/api/records", json={"record_type": "visit", "title": "Eye test", "record_date": "2026-02-01"})
    user_a.post("/api/emergency/open")
    kinds = {e["kind"] for e in user_a.get("/api/timeline").json()}
    assert {"record", "emergency"} <= kinds


def test_security_headers(client):
    r = client.get("/api/system/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
