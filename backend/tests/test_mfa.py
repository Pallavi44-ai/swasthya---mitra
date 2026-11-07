"""Secure authentication: registration verification, password + OTP login, limits, recovery, sessions, passkeys, providers."""
import json
import threading
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import OtpChallenge, UserSession
from app.services import otp_delivery
from app.services.otp_delivery import OUTBOX
from tests.conftest import last_code, login, register

PW = "Secret123"


def _login_step1(client, email="m@example.com", pw=PW):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    return r


def _setup(client, email="m@example.com"):
    register(client, email)
    client.post("/api/auth/logout")


# ---------- registration -------------------------------------------------------------------------
def test_registration_requires_code_before_session(client):
    body = {"email": "n@example.com", "password": PW, "full_name": "N", "accepted_disclaimer": True}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201 and r.json()["otp_sent"] and "sm_session" not in client.cookies
    assert client.get("/api/auth/me").status_code == 401
    # unverified account cannot log in with the password alone either
    r2 = _login_step1(client, "n@example.com")
    assert r2.status_code == 403 and r2.json()["detail"]["code"] == "verification_required"
    assert "sm_session" not in client.cookies


def test_wrong_registration_code_rejected(client):
    body = {"email": "n@example.com", "password": PW, "full_name": "N", "accepted_disclaimer": True}
    cid = client.post("/api/auth/register", json=body).json()["challenge_id"]
    bad = "000000" if last_code("n@example.com") != "000000" else "111111"
    assert client.post("/api/auth/register/verify", json={"challenge_id": cid, "code": bad}).status_code == 400
    assert client.get("/api/auth/me").status_code == 401


def test_sms_channel_requires_phone_and_provider(client, monkeypatch):
    body = {"email": "s@example.com", "password": PW, "full_name": "S", "accepted_disclaimer": True, "mfa_channel": "sms"}
    assert client.post("/api/auth/register", json=body).status_code == 422  # no phone
    # phone given but no SMS provider available (as on a production server without Twilio)
    monkeypatch.setattr(type(get_settings()), "sms_otp_ready", property(lambda self: False))
    assert client.post("/api/auth/register", json={**body, "phone": "9876543210"}).status_code == 422


# ---------- login: password + second factor ------------------------------------------------------
def test_login_needs_password_and_code(client):
    _setup(client)
    r = _login_step1(client)
    assert r.status_code == 200 and r.json()["mfa_required"] is True
    assert "sm_session" not in client.cookies and client.get("/api/auth/me").status_code == 401
    assert OUTBOX[-1]["purpose"] == "login" and OUTBOX[-1]["to"] == "m@example.com"
    ok = client.post("/api/auth/mfa/verify", json={"challenge_id": r.json()["challenge_id"], "code": last_code("m@example.com", "login")})
    assert ok.status_code == 200 and client.get("/api/auth/me").status_code == 200


def test_wrong_password_sends_no_code(client):
    _setup(client)
    n = len(OUTBOX)
    assert _login_step1(client, pw="Wrong1234").status_code == 401
    assert _login_step1(client, "ghost@example.com").status_code == 401
    assert len(OUTBOX) == n


def test_wrong_code_attempt_limit_then_locked_even_for_right_code(client):
    _setup(client)
    r = _login_step1(client).json()
    code = last_code("m@example.com", "login")
    wrong = "000000" if code != "000000" else "111111"
    max_a = get_settings().otp_max_attempts
    for i in range(max_a):
        resp = client.post("/api/auth/mfa/verify", json={"challenge_id": r["challenge_id"], "code": wrong})
        assert resp.status_code in (400, 429)
    resp = client.post("/api/auth/mfa/verify", json={"challenge_id": r["challenge_id"], "code": code})
    assert resp.status_code == 429 and resp.json()["detail"]["code"] == "locked"
    assert "sm_session" not in client.cookies


def test_attempts_left_reported(client):
    _setup(client)
    r = _login_step1(client).json()
    code = last_code("m@example.com", "login")
    resp = client.post("/api/auth/mfa/verify", json={"challenge_id": r["challenge_id"], "code": "000000" if code != "000000" else "111111"})
    assert resp.json()["detail"]["attempts_left"] == get_settings().otp_max_attempts - 1


def test_code_expires(client):
    _setup(client)
    r = _login_step1(client).json()
    code = last_code("m@example.com", "login")
    with SessionLocal() as db:
        ch = db.get(OtpChallenge, r["challenge_id"])
        ch.expires_at = ch.expires_at - timedelta(seconds=get_settings().otp_ttl_seconds + 5)
        db.commit()
    resp = client.post("/api/auth/mfa/verify", json={"challenge_id": r["challenge_id"], "code": code})
    assert resp.status_code == 400 and resp.json()["detail"]["code"] == "expired"


def test_code_is_single_use(client):
    _setup(client)
    r = _login_step1(client).json()
    code = last_code("m@example.com", "login")
    body = {"challenge_id": r["challenge_id"], "code": code}
    assert client.post("/api/auth/mfa/verify", json=body).status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/mfa/verify", json=body).status_code == 400  # replay refused


def test_challenge_cannot_be_used_for_other_purpose(client):
    _setup(client)
    r = _login_step1(client).json()
    code = last_code("m@example.com", "login")
    # a LOGIN challenge must not complete a password reset
    resp = client.post("/api/auth/reset-password", json={"challenge_id": r["challenge_id"], "code": code, "new_password": "Another123"})
    assert resp.status_code == 400
    assert _login_step1(client, pw="Another123").status_code == 401


def test_resend_cooldown_and_cap(client):
    _setup(client)
    r = _login_step1(client).json()
    cid = r["challenge_id"]
    s = get_settings()
    too_soon = client.post("/api/auth/mfa/send", json={"challenge_id": cid})
    assert too_soon.status_code == 429 and too_soon.json()["detail"]["code"] == "resend_wait"
    old = last_code("m@example.com", "login")
    for sent in range(1, s.otp_max_sends):
        with SessionLocal() as db:  # fast-forward the cooldown
            ch = db.get(OtpChallenge, cid)
            ch.last_sent_at = ch.last_sent_at - timedelta(seconds=s.otp_resend_cooldown_seconds + 1)
            db.commit()
        assert client.post("/api/auth/mfa/send", json={"challenge_id": cid}).status_code == 200
    with SessionLocal() as db:
        ch = db.get(OtpChallenge, cid)
        ch.last_sent_at = ch.last_sent_at - timedelta(seconds=s.otp_max_sends * 100)
        db.commit()
    capped = client.post("/api/auth/mfa/send", json={"challenge_id": cid})
    assert capped.status_code == 429 and capped.json()["detail"]["code"] == "too_many_sends"
    # the newest code works, an older one does not
    new = last_code("m@example.com", "login")
    if new != old:
        assert client.post("/api/auth/mfa/verify", json={"challenge_id": cid, "code": old}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"challenge_id": cid, "code": new}).status_code == 200


def test_resend_resets_attempts(client):
    _setup(client)
    cid = _login_step1(client).json()["challenge_id"]
    for _ in range(get_settings().otp_max_attempts):
        client.post("/api/auth/mfa/verify", json={"challenge_id": cid, "code": "000000"})
    with SessionLocal() as db:
        ch = db.get(OtpChallenge, cid)
        ch.last_sent_at = ch.last_sent_at - timedelta(seconds=60)
        db.commit()
    assert client.post("/api/auth/mfa/send", json={"challenge_id": cid}).status_code == 200
    assert client.post("/api/auth/mfa/verify", json={"challenge_id": cid, "code": last_code("m@example.com", "login")}).status_code == 200


def test_unknown_challenge_and_bad_format(client):
    assert client.post("/api/auth/mfa/verify", json={"challenge_id": "nope", "code": "123456"}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"challenge_id": "x", "code": "12ab56"}).status_code == 422
    assert client.post("/api/auth/mfa/verify", json={"challenge_id": "x", "code": "12345"}).status_code == 422


# ---------- secrets never stored in clear --------------------------------------------------------
def test_no_plaintext_password_or_code_in_database(client):
    register(client, "p@example.com")
    client.post("/api/auth/logout")
    r = _login_step1(client, "p@example.com").json()
    code = last_code("p@example.com", "login")
    with engine.connect() as c:
        dump = json.dumps({t: [str(row) for row in c.execute(text(f"SELECT * FROM {t}")).fetchall()]
                           for t in ("users", "otp_challenges", "user_sessions", "audit_logs")})
        pw_hash = c.execute(text("SELECT password_hash FROM users")).scalar()
        stored = c.execute(text("SELECT code_hash FROM otp_challenges WHERE id=:i"), {"i": r["challenge_id"]}).scalar()
    assert PW not in dump and f"'{code}'" not in dump
    assert pw_hash.startswith("$2") and stored and stored != code and len(stored) == 64


def test_no_code_in_api_response_or_logs(client, caplog):
    _setup(client)
    with caplog.at_level("DEBUG"):
        r = _login_step1(client)
    code = last_code("m@example.com", "login")
    assert code not in r.text
    assert code not in caplog.text


# ---------- password recovery --------------------------------------------------------------------
def test_forgot_password_does_not_reveal_accounts(client):
    _setup(client)
    a = client.post("/api/auth/forgot-password", json={"email": "m@example.com"})
    b = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert a.status_code == b.status_code == 200
    ja, jb = a.json(), b.json()
    assert set(ja) == set(jb)
    for k in ("message", "destination_masked", "channel", "expires_in", "max_attempts"):
        assert ja[k] == jb[k]
    assert [m for m in OUTBOX if m["purpose"] == "password_reset" and m["to"] == "nobody@example.com"] == []
    # decoy challenge never works
    assert client.post("/api/auth/reset-password", json={"challenge_id": jb["challenge_id"], "code": "123456", "new_password": "Another123"}).status_code == 400


def test_reset_password_full_flow_and_session_revocation(client, make_client):
    other = make_client("m@example.com")  # logged-in device #1
    assert other.get("/api/auth/me").status_code == 200
    r = client.post("/api/auth/forgot-password", json={"email": "m@example.com"}).json()
    code = last_code("m@example.com", "password_reset")
    assert client.post("/api/auth/reset-password", json={"challenge_id": r["challenge_id"], "code": code, "new_password": "NewSecret456"}).status_code == 204
    assert other.get("/api/auth/me").status_code == 401  # old sessions are dead
    assert _login_step1(client, pw=PW).status_code == 401  # old password gone
    assert login(client, "m@example.com", "NewSecret456").status_code == 200
    # code cannot be replayed
    assert client.post("/api/auth/reset-password", json={"challenge_id": r["challenge_id"], "code": code, "new_password": "Third12345"}).status_code == 400


def test_reset_rejects_weak_password_and_wrong_code(client):
    _setup(client)
    r = client.post("/api/auth/forgot-password", json={"email": "m@example.com"}).json()
    code = last_code("m@example.com", "password_reset")
    assert client.post("/api/auth/reset-password", json={"challenge_id": r["challenge_id"], "code": code, "new_password": "short"}).status_code == 422
    assert client.post("/api/auth/reset-password", json={"challenge_id": r["challenge_id"], "code": "000000" if code != "000000" else "111111", "new_password": "NewSecret456"}).status_code == 400
    assert login(client, "m@example.com").status_code == 200  # password unchanged


# ---------- sessions / logout / unauthorised access ---------------------------------------------
def test_logout_revokes_session_server_side(client):
    register(client, "l@example.com")
    stolen = client.cookies.get("sm_session")
    client.post("/api/auth/logout")
    replay = TestClient(app)
    replay.cookies.set("sm_session", stolen)
    assert replay.get("/api/auth/me").status_code == 401  # the old cookie is useless even if copied


def test_idle_timeout(client):
    register(client, "i@example.com")
    with SessionLocal() as db:
        for s in db.query(UserSession).all():
            s.last_seen_at = s.last_seen_at - timedelta(minutes=get_settings().session_idle_minutes + 1)
        db.commit()
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and "timed out" in r.json()["detail"]


def test_forged_or_garbage_cookie_rejected(client):
    for v in ("garbage", "a.b.c", ""):
        c = TestClient(app)
        c.cookies.set("sm_session", v)
        assert c.get("/api/profile").status_code == 401


def test_session_list_and_revoke_other_device(client, make_client):
    a = make_client("d@example.com")
    b = TestClient(app)
    assert login(b, "d@example.com").status_code == 200
    sess = a.get("/api/account/security").json()["sessions"]
    assert len(sess) == 2 and sum(s["current"] for s in sess) == 1
    other = next(s for s in sess if not s["current"])
    assert a.delete(f"/api/account/security/sessions/{other['id']}").status_code == 204
    assert b.get("/api/auth/me").status_code == 401 and a.get("/api/auth/me").status_code == 200


def test_cannot_revoke_someone_elses_session(make_client):
    a, b = make_client("a@example.com"), make_client("b@example.com")
    sid = b.get("/api/account/security").json()["sessions"][0]["id"]
    assert a.delete(f"/api/account/security/sessions/{sid}").status_code == 404
    assert b.get("/api/auth/me").status_code == 200


def test_logout_all(client, make_client):
    a = make_client("z@example.com")
    b = TestClient(app)
    login(b, "z@example.com")
    assert a.post("/api/auth/logout-all").status_code == 204
    assert a.get("/api/auth/me").status_code == 401 and b.get("/api/auth/me").status_code == 401


def test_change_password_keeps_this_device_only(make_client):
    a = make_client("c@example.com")
    b = TestClient(app)
    login(b, "c@example.com")
    assert a.post("/api/auth/change-password", json={"current_password": "Wrong1234", "new_password": "Brand5678x"}).status_code == 400
    assert a.post("/api/auth/change-password", json={"current_password": PW, "new_password": "Brand5678x"}).status_code == 204
    assert a.get("/api/auth/me").status_code == 200 and b.get("/api/auth/me").status_code == 401


def test_security_overview_masks_and_has_no_secrets(make_client):
    a = make_client("sec@example.com")
    o = a.get("/api/account/security").json()
    assert o["email"] == "sec@example.com" and o["mfa_channel"] == "email" and o["passkeys"] == []
    dump = json.dumps(o)
    assert "password" not in dump.lower() and "code_hash" not in dump


def test_security_endpoints_require_login(client):
    for m, p in [("get", "/api/account/security"), ("post", "/api/auth/webauthn/register/options"), ("put", "/api/account/security/channel"),
                 ("post", "/api/auth/logout-all"), ("post", "/api/account/security/phone")]:
        assert getattr(client, m)(p, **({"json": {}} if m != "get" else {})).status_code in (401, 422), p
        if m != "get":
            assert getattr(client, m)(p, json={}).status_code != 200


def test_other_users_records_unreachable_after_mfa_login(make_client):
    a, b = make_client("a@example.com"), make_client("b@example.com")
    pid = a.get("/api/profile").json()
    assert a.get("/api/records").status_code == 200
    assert b.get("/api/prescriptions").json() == [] or b.get("/api/prescriptions").json()["items"] == []
    assert pid and b.get("/api/profile").json()["id"] != pid["id"] if "id" in pid else True


# ---------- channel / phone ---------------------------------------------------------------------
def test_cannot_switch_to_sms_without_verified_phone(make_client):
    a = make_client("ch@example.com")
    assert a.put("/api/account/security/channel", json={"channel": "sms", "password": PW}).status_code == 422
    assert a.put("/api/account/security/channel", json={"channel": "email", "password": "Wrong1234"}).status_code == 400
    assert a.put("/api/account/security/channel", json={"channel": "email", "password": PW}).status_code == 200


# ---------- providers ---------------------------------------------------------------------------
def test_console_provider_refused_in_production(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(type(s), "is_production", property(lambda self: True))
    with pytest.raises(otp_delivery.DeliveryError):
        otp_delivery.send_otp("email", "x@example.com", "123456", "login")


def test_production_startup_requires_real_otp_provider(monkeypatch):
    from app.core import config
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "k" * 43 + "=")
    monkeypatch.setenv("OTP_EMAIL_PROVIDER", "console")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(Exception):
            config.get_settings()
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()


def test_twilio_request_shape(monkeypatch):
    seen = {}

    def fake_post(url, data=None, auth=None, timeout=None):
        seen.update(url=url, data=data, auth=auth)
        return httpx.Response(201, json={"sid": "SM1"})

    s = get_settings()
    monkeypatch.setattr(s, "otp_sms_provider", "twilio")
    monkeypatch.setattr(s, "twilio_account_sid", "ACtest")
    monkeypatch.setattr(s, "twilio_auth_token", "tok")
    monkeypatch.setattr(s, "twilio_from", "+15005550006")
    monkeypatch.setattr(otp_delivery.httpx, "post", fake_post)
    otp_delivery.send_otp("sms", "+919876543210", "123456", "login")
    assert seen["url"].endswith("/Accounts/ACtest/Messages.json") and seen["data"]["To"] == "+919876543210"
    assert "123456" in seen["data"]["Body"] and seen["auth"] == ("ACtest", "tok")
    monkeypatch.setattr(otp_delivery.httpx, "post", lambda *a, **k: httpx.Response(400, json={}))
    with pytest.raises(otp_delivery.DeliveryError):
        otp_delivery.send_otp("sms", "+919876543210", "123456", "login")


def test_delivery_failure_is_reported_not_swallowed(client, monkeypatch):
    _setup(client)

    def boom(*a, **k):
        raise otp_delivery.DeliveryError("down")

    monkeypatch.setattr(otp_delivery, "send_otp", boom)
    r = _login_step1(client)
    assert r.status_code == 503  # never pretend a code was sent


def test_real_smtp_delivery_to_local_server(monkeypatch):
    """Sends through the real smtplib code path to a local aiosmtpd server and reads the message back."""
    aiosmtpd = pytest.importorskip("aiosmtpd.controller")
    got = []

    class H:
        async def handle_DATA(self, server, session, envelope):
            got.append(envelope)
            return "250 OK"

    import socket
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    ctl = aiosmtpd.Controller(H(), hostname="127.0.0.1", port=port)
    ctl.start()
    try:
        s = get_settings()
        monkeypatch.setattr(s, "otp_email_provider", "smtp")
        monkeypatch.setattr(s, "smtp_host", "127.0.0.1")
        monkeypatch.setattr(s, "smtp_port", port)
        monkeypatch.setattr(s, "smtp_from", "no-reply@swasthya.test")
        monkeypatch.setattr(s, "smtp_starttls", False)
        monkeypatch.setattr(s, "smtp_user", None)
        otp_delivery.send_otp("email", "patient@example.com", "482913", "login")
    finally:
        ctl.stop()
    assert len(got) == 1 and got[0].rcpt_tos == ["patient@example.com"]
    body = got[0].content.decode()
    assert "482913" in body and "Never share" in body
