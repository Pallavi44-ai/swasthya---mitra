"""Prescription OCR pipeline (real Tesseract on a synthetic image), confirmation gate, reminders & adherence."""
import io
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.services import ocr, prescription_parser as pp
from tests.conftest import register
from tests.helpers import SAMPLE_LINES, gemini_text_response, install_fake_gemini, prescription_image

needs_tesseract = pytest.mark.skipif(not ocr.run_ocr(ocr.load_image(prescription_image(["test"]))).available, reason="tesseract not installed")


def upload(client, data, name="rx.jpg", mime="image/jpeg"):
    return client.post("/api/prescriptions", files={"file": (name, data, mime)})


# ---- parser & explainer (pure functions) --------------------------------------------------------
def test_parse_line_extracts_only_whats_written():
    it = pp.parse_line("1) Tab Metformin 500mg 1-0-1 after food x 30 days", 0.95)
    assert (it.medicine_name, it.strength, it.frequency_text, it.duration_text) == ("Metformin", "500mg", "1-0-1", "x 30 days")
    assert it.dosage_instruction == "1-0-1 after food" and it.form == "tablet" and it.flags == []


def test_parse_line_flags_missing_values_instead_of_guessing():
    it = pp.parse_line("Tab Telmisartan", 0.9)
    assert it.strength is None and it.dosage_instruction is None
    assert {"strength_not_found", "dosage_instruction_not_found"} <= set(it.flags)
    assert pp.parse_line("Date: 12/10/2026") is None and pp.parse_line("Dr. Ramesh Kumar MBBS") is None
    assert pp.parse_line("Follow up after two weeks") is None


def test_explain_instruction_multilingual():
    e = pp.explain_instruction("1-0-1 after food", "en")
    assert e["lines"] == ["Morning: 1 (after food)", "Afternoon: 0", "Night: 1 (after food)"] and e["suggested_times"] == ["08:00", "21:00"]
    assert "सुबह" in pp.explain_instruction("1-0-1", "hi")["lines"][0]
    assert pp.explain_instruction("BD", "en")["suggested_times"] == ["08:00", "20:00"]
    assert pp.explain_instruction("SOS", "en")["as_needed"] is True
    assert pp.explain_instruction("as directed by doctor")["parsed"] is False  # unknown → no guessing


# ---- upload pipeline ----------------------------------------------------------------------------
@needs_tesseract
def test_upload_extracts_medicines_with_confidence(user_a):
    r = upload(user_a, prescription_image(SAMPLE_LINES))
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "extracted" and p["extraction_engine"] == "tesseract-rules"
    names = {i["medicine_name"].lower(): i for i in p["items"]}
    assert {"metformin", "amlodipine", "omeprazole"} <= set(names)
    m = names["metformin"]
    assert m["strength"] == "500mg" and m["dosage_instruction"].startswith("1-0-1") and 0 < m["confidence"] <= 1
    assert m["user_confirmed"] is False
    assert p["doctor_name"] and "Ramesh" in p["doctor_name"] and p["prescribed_date"] == "2026-10-12"
    assert "ai_consent_off_local_only" not in p["warnings"] and "ai_not_configured_local_only" in p["warnings"]
    assert p["has_image"] is False  # store_prescription_images consent not granted


@needs_tesseract
def test_blurry_or_blank_image_flags_uncertainty(user_a):
    p = upload(user_a, prescription_image(SAMPLE_LINES, blur=9)).json()
    assert "image_blurry" in p["warnings"]
    if p["status"] == "failed":
        assert p["items"] == [] and "clearer" in p["message"]
    blank = upload(user_a, prescription_image([])).json()
    assert blank["status"] == "failed" and blank["items"] == []


def test_upload_validation(user_a):
    assert upload(user_a, b"not an image").status_code == 422
    assert upload(user_a, b"").status_code == 422
    import app.core.config as cfg
    big = prescription_image(["x"], size=(300, 300)) + b"0" * (9 * 1024 * 1024)
    assert upload(user_a, big).status_code == 413


@needs_tesseract
def test_stored_image_is_encrypted_and_consent_gated(client):
    register(client, consents={"store_prescription_images": True})
    p = upload(client, prescription_image(SAMPLE_LINES)).json()
    assert p["has_image"]
    img = client.get(f"/api/prescriptions/{p['id']}/image")
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"
    from app.db.session import SessionLocal
    from app.models import Prescription
    with SessionLocal() as db:
        raw = open(db.get(Prescription, p["id"]).image_path, "rb").read()
    assert raw[:2] != b"\xff\xd8"  # ciphertext on disk, not a JPEG


def test_gemini_extraction_is_grounded_and_flags_unverified(user_a):
    lines = ["Dr. Meena Rao", "Tab Metformin 500mg 1-0-1 after food x 30 days"]
    def handler(req):
        body = json.loads(req.content)
        assert any("inlineData" in p for p in body["contents"][0]["parts"])  # image really sent as multimodal part
        return gemini_text_response({"doctor_name": "Dr. Meena Rao", "prescribed_date": None, "legibility": "good", "medicines": [
            {"name": "Metformin", "strength": "500mg", "dosage_instruction": "1-0-1 after food", "duration": "30 days", "confidence": 0.95, "unclear_fields": []},
            {"name": "Zorbaxin", "strength": None, "dosage_instruction": "1-0-0", "confidence": 0.9, "unclear_fields": ["strength"]},  # hallucination, absent from OCR text
        ]})
    install_fake_gemini(handler)
    p = upload(user_a, prescription_image(lines)).json()
    by = {i["medicine_name"]: i for i in p["items"]}
    assert p["extraction_engine"] == "gemini+tesseract" if ocr.run_ocr(ocr.load_image(prescription_image(lines))).available else True
    assert by["Metformin"]["confidence"] > by["Zorbaxin"]["confidence"]
    assert "name_not_found_in_ocr_text" in by["Zorbaxin"]["flags"] and by["Zorbaxin"]["needs_review"] is True
    assert "unclear:strength" in by["Zorbaxin"]["flags"] and "strength_not_found" in by["Zorbaxin"]["flags"]


def test_gemini_failure_falls_back_to_local_parser(user_a):
    install_fake_gemini(lambda req: httpx.Response(500, json={}))
    import app.services.gemini as g
    g.time.sleep = lambda *_: None
    p = upload(user_a, prescription_image(SAMPLE_LINES)).json()
    assert "ai_extraction_failed_used_local_parser" in p["warnings"]


# ---- confirmation gate & reminders --------------------------------------------------------------
def make_prescription(client):
    """Manual entry path (works without OCR): create an empty prescription via a blank upload, then add items."""
    p = upload(client, prescription_image([])).json()
    assert p["status"] == "failed"
    r = client.post(f"/api/prescriptions/{p['id']}/items", json={"medicine_name": "Metformin", "strength": "500mg", "dosage_instruction": "1-0-1 after food", "duration_text": "30 days"})
    assert r.status_code == 201
    return r.json()


def test_reminder_blocked_until_user_confirms(user_a):
    p = make_prescription(user_a)
    item = p["items"][0]
    body = {"prescription_item_id": item["id"], "times": ["08:00", "21:00"]}
    r = user_a.post("/api/reminders", json=body)
    assert r.status_code == 409 and "confirmed" in r.json()["detail"]
    assert user_a.get("/api/reminders/eligible").json() == []
    # acknowledgement is mandatory
    assert user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [item["id"]], "acknowledged": False}).status_code == 422
    assert user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [], "acknowledged": True}).status_code == 422
    assert user_a.post("/api/reminders", json=body).status_code == 409  # still blocked


def test_cannot_confirm_item_without_dosage(user_a):
    p = make_prescription(user_a)
    r = user_a.post(f"/api/prescriptions/{p['id']}/items", json={"medicine_name": "Telmisartan"}).json()
    bad = [i for i in r["items"] if i["medicine_name"] == "Telmisartan"][0]
    resp = user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [bad["id"]], "acknowledged": True})
    assert resp.status_code == 422 and "dosage" in json.dumps(resp.json()).lower()
    fixed = user_a.put(f"/api/prescriptions/{p['id']}/items/{bad['id']}", json={"medicine_name": "Telmisartan", "dosage_instruction": "0-0-1"})
    assert fixed.status_code == 200
    assert user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [bad["id"]], "acknowledged": True}).status_code == 200


def test_full_flow_confirm_remind_take_adherence(user_a):
    p = make_prescription(user_a)
    iid = p["items"][0]["id"]
    ex = user_a.get(f"/api/prescriptions/{p['id']}/items/{iid}/explain?lang=en").json()
    assert ex["suggested_times"] == ["08:00", "21:00"]
    user_a.put("/api/profile", json={"allergies": ["metformin"]})
    c = user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [iid], "acknowledged": True}).json()
    assert c["prescription"]["status"] == "confirmed" and c["allergy_warnings"] and "allergy" in c["allergy_warnings"][0]
    assert user_a.put(f"/api/prescriptions/{p['id']}/items/{iid}", json={"medicine_name": "Changed"}).status_code == 409  # locked
    assert user_a.get("/api/reminders/eligible").json()[0]["prescription_item_id"] == iid

    # Reminder: dose text is copied verbatim from the confirmed item
    all_day = ["00:01", "23:58"]
    r = user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": all_day})
    assert r.status_code == 201 and r.json()["dosage_instruction"] == "1-0-1 after food" and r.json()["medicine_name"] == "Metformin"
    assert user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": all_day}).status_code == 409  # duplicate
    assert user_a.get("/api/reminders/eligible").json() == []

    today = user_a.get("/api/reminders/today").json()
    assert len(today["doses"]) >= 1 and all(d["dosage_instruction"] == "1-0-1 after food" for d in today["doses"])
    due = user_a.get("/api/reminders/due").json()
    for d in due:
        assert user_a.post(f"/api/reminders/doses/{d['id']}", json={"status": "taken"}).json()["status"] == "taken"
    assert user_a.get("/api/reminders/due").json() == []
    adh = user_a.get("/api/reminders/adherence?days=7").json()
    assert adh["taken"] == len(due) and adh["missed"] == 0 and (adh["percent"] == 100 if due else adh["percent"] is None)

    # deactivate removes future pending doses
    rid = r.json()["id"]
    assert user_a.patch(f"/api/reminders/{rid}", json={"active": False}).json()["active"] is False
    assert user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": ["09:00"]}).status_code == 201
    assert user_a.delete(f"/api/reminders/{rid}").status_code == 204


def test_reminder_validation(user_a):
    p = make_prescription(user_a)
    iid = p["items"][0]["id"]
    user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [iid], "acknowledged": True})
    assert user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": ["25:00"]}).status_code == 422
    assert user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": []}).status_code == 422
    assert user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": ["08:00"], "start_date": "2026-05-02", "end_date": "2026-05-01"}).status_code == 422
    assert user_a.post("/api/reminders", json={"prescription_item_id": "nope", "times": ["08:00"]}).status_code == 404


def test_overdue_doses_become_missed_and_future_cannot_be_marked(user_a):
    from app.db.session import SessionLocal
    from app.models import DoseLog

    p = make_prescription(user_a)
    iid = p["items"][0]["id"]
    user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [iid], "acknowledged": True})
    rid = user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": ["08:00"]}).json()["id"]
    user_a.get("/api/reminders/today")
    with SessionLocal() as db:
        d = db.query(DoseLog).first()
        old = DoseLog(reminder_id=d.reminder_id, user_id=d.user_id, scheduled_at=datetime.now(timezone.utc) - timedelta(hours=5))
        db.add(old)
        db.commit()
        fut = db.query(DoseLog).filter(DoseLog.scheduled_at > datetime.now(timezone.utc) + timedelta(hours=2)).first()
        fut_id = fut.id
    assert user_a.get("/api/reminders/adherence?days=1").json()["missed"] == 1
    assert user_a.post(f"/api/reminders/doses/{fut_id}", json={"status": "taken"}).status_code == 409


def test_prescription_and_reminder_isolation(make_client):
    a, b = make_client("a@example.com"), make_client("b@example.com")
    p = make_prescription(a)
    iid = p["items"][0]["id"]
    a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [iid], "acknowledged": True})
    assert b.get(f"/api/prescriptions/{p['id']}").status_code == 404
    assert b.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [iid], "acknowledged": True}).status_code == 404
    assert b.post("/api/reminders", json={"prescription_item_id": iid, "times": ["08:00"]}).status_code == 404
    assert b.get("/api/prescriptions").json() == []


def test_delete_prescription_cascades_to_reminders(user_a):
    p = make_prescription(user_a)
    iid = p["items"][0]["id"]
    user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [iid], "acknowledged": True})
    user_a.post("/api/reminders", json={"prescription_item_id": iid, "times": ["08:00"]})
    assert user_a.delete(f"/api/prescriptions/{p['id']}").status_code == 204
    assert user_a.get("/api/reminders").json() == []


def test_emergency_share_message_respects_consent(client):
    register(client, consents={"emergency_sharing": False})
    client.post("/api/contacts", json={"name": "Son", "phone": "+919876543210"})
    r = client.post("/api/emergency/share-message", json={"latitude": 12.97, "longitude": 77.59}).json()
    assert "maps.google" not in r["message"] and r["location_included"] is False
    client.put("/api/consents", json={"consents": {"emergency_sharing": True}})
    r = client.post("/api/emergency/share-message", json={"latitude": 12.97, "longitude": 77.59}).json()
    assert "12.97000,77.59000" in r["message"] and r["contacts"][0]["tel_href"] == "tel:+919876543210"
    info = client.get("/api/emergency").json()
    assert info["numbers"][0]["number"] == "108" and info["contacts"]
