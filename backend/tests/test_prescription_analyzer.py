"""Prescription Analyzer: preprocessing, strict validation of the vision model's reply, Clear/Check/Unclear status,
uncertainty handling, encrypted storage of the new details, backward compatibility and the confirmation gate.

The vision model is replaced by a fake HTTP transport (nothing here calls Google), so these tests prove how the app
treats model output – they say nothing about how accurately the real model reads handwriting.
"""
import io
import json

import httpx
import pytest
from PIL import Image, ImageOps
from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models import Prescription, PrescriptionItem, User
from app.services import ocr, prescription_service as ps
from app.services.gemini import GeminiError
from tests.helpers import SAMPLE_LINES, gemini_text_response, install_fake_gemini, prescription_image

needs_tesseract = pytest.mark.skipif(
    not ocr.run_ocr(ocr.load_image(prescription_image(["test"]))).available, reason="tesseract not installed")


def upload(client, data, name="rx.jpg", mime="image/jpeg"):
    return client.post("/api/prescriptions", files={"file": (name, data, mime)})


def fake_ai(payload):
    """Install a fake Gemini that returns `payload` (dict -> JSON, str -> raw text) for every call."""
    install_fake_gemini(lambda req: gemini_text_response(payload))


FULL_REPLY = {
    "doctor_name": "Dr. Meena Rao", "prescribed_date": "2026-10-12", "legibility": "good",
    "patient": {"name": "Asha Verma", "age": 67, "sex": "F"},
    "prescriber": {"name": "Dr. Meena Rao", "qualification": "MBBS", "registration_number": "KMC 12345", "clinic": "City Clinic"},
    "diagnosis": "Type 2 diabetes",
    "warnings": ["Bottom edge of the page is cut off"],
    "full_transcription": "Dr. Meena Rao MBBS\nTab Metformin 500mg 1-0-1 after food x 30 days",
    "medicines": [{
        "name": "Metformin", "strength": "500mg", "form": "tablet", "dosage_instruction": "1-0-1 after food", "frequency": "1-0-1",
        "duration": "30 days", "additional_instructions": "with warm water", "raw_text": "Tab Metformin 500mg 1-0-1 after food x 30 days",
        "uncertainty_note": None, "confidence": 0.95, "unclear_fields": [],
    }],
}


# ---- preprocessing -------------------------------------------------------------------------------
def _jpeg(img: Image.Image, exif_orientation: int | None = None) -> bytes:
    buf = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def test_exif_orientation_is_applied():
    wide = Image.new("RGB", (600, 300), "white")
    assert ocr.load_image(_jpeg(wide, exif_orientation=6)).size == (300, 600)  # 6 = rotated 90 degrees
    assert ocr.load_image(_jpeg(wide)).size == (600, 300)


def test_large_photos_are_downscaled_and_bad_files_rejected():
    big = Image.new("RGB", (4000, 3000), "white")
    assert max(ocr.load_image(_jpeg(big)).size) <= ocr.MAX_SIDE
    for junk in (b"not an image at all", b"%PDF-1.4 fake"):
        with pytest.raises(ocr.ImageError):
            ocr.load_image(junk)


def test_enhance_for_model_raises_contrast_without_changing_size():
    faint = Image.new("RGB", (800, 600), (170, 170, 170))
    for x in range(100, 700, 10):  # faint "writing" strokes
        for y in range(100, 500):
            faint.putpixel((x, y), (140, 140, 140))
    before = ImageOps.grayscale(faint)
    after = ImageOps.grayscale(ocr.enhance_for_model(faint, []))
    assert after.size == before.size
    assert after.getextrema()[1] - after.getextrema()[0] > before.getextrema()[1] - before.getextrema()[0]


def test_enhance_sharpens_only_when_the_photo_was_flagged_blurry():
    img = ocr.load_image(prescription_image(SAMPLE_LINES, blur=2.0))
    plain, sharp = ocr.enhance_for_model(img, []), ocr.enhance_for_model(img, ["blurry"])
    assert list(plain.getdata()) != list(sharp.getdata())
    assert plain.size == sharp.size == img.size


@needs_tesseract
@pytest.mark.parametrize("angle", [90, 180, 270])
def test_sideways_photo_is_turned_upright(angle):
    upright = ocr.load_image(prescription_image(SAMPLE_LINES))
    fixed, turned = ocr.fix_rotation(upright.rotate(angle, expand=True))
    assert turned == angle
    assert "Metformin" in ocr.run_ocr(fixed).text


@needs_tesseract
def test_upright_photo_is_left_alone():
    img = ocr.load_image(prescription_image(SAMPLE_LINES))
    assert ocr.fix_rotation(img)[1] == 0


def test_rotation_fix_never_breaks_when_the_detector_is_missing(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", None)  # import fails -> must fall back silently
    img = Image.new("RGB", (100, 100), "white")
    assert ocr.fix_rotation(img) == (img, 0)


def test_rotated_photo_is_reported_to_the_user(user_a):
    pytest.importorskip("pytesseract")
    if not ocr.run_ocr(ocr.load_image(prescription_image(["x"]))).available:
        pytest.skip("tesseract not installed")
    img = ocr.load_image(prescription_image(SAMPLE_LINES)).rotate(90, expand=True)
    p = upload(user_a, _jpeg(img)).json()
    assert "image_rotated_automatically" in p["warnings"] and p["quality"]["rotated_degrees"] == 90


# ---- strict validation of the model reply ---------------------------------------------------------
def test_valid_reply_is_accepted_with_all_fields():
    meds, page, dropped = ps.validate_ai_response(FULL_REPLY)
    assert dropped == 0 and meds[0]["medicine_name"] == "Metformin" and meds[0]["raw_text"].startswith("Tab Metformin")
    assert page.patient.as_dict() == {"name": "Asha Verma", "age": "67", "sex": "F"}  # numeric age kept as text
    assert page.diagnosis == "Type 2 diabetes" and page.warnings == ["Bottom edge of the page is cut off"]


@pytest.mark.parametrize("bad", [None, [], "text", 42, {}, {"medicines": "none"}, {"medicines": {"name": "x"}}, {"legibility": "good"}])
def test_unusable_reply_structure_raises(bad):
    with pytest.raises(GeminiError):
        ps.validate_ai_response(bad)


def test_bad_values_become_none_not_guesses():
    meds, page, dropped = ps.validate_ai_response({"legibility": "ugly", "doctor_name": 5, "warnings": "nope", "patient": "Asha", "medicines": [
        {"name": "Metformin", "strength": 500, "dosage_instruction": ["1-0-1"], "confidence": "high", "unclear_fields": "strength"},
        {"name": "Amlodipine", "confidence": 7, "raw_text": "x" * 5000, "extra_junk": {"a": 1}},
        {"name": "Omeprazole", "confidence": True},
    ]})
    assert dropped == 0 and page.legibility == "fair" and page.doctor_name is None and page.warnings == [] and page.patient is None
    m = {x["medicine_name"]: x for x in meds}
    assert m["Metformin"]["strength"] is None and m["Metformin"]["dosage_instruction"] is None  # wrong types are dropped, not converted
    assert m["Metformin"]["model_conf"] == 0.5 and m["Metformin"]["unclear"] == []
    assert m["Amlodipine"]["model_conf"] == 0.5 and len(m["Amlodipine"]["raw_text"]) == 300
    assert m["Omeprazole"]["model_conf"] == 0.5  # a boolean is not a confidence


def test_lines_without_a_readable_name_or_not_objects_are_dropped():
    meds, _, dropped = ps.validate_ai_response({"legibility": "poor", "medicines": [
        {"name": None, "confidence": 0.2}, {"name": "  ", "confidence": 0.9}, "garbage", 7, None, {"name": "Metformin", "confidence": 0.9}]})
    assert [m["medicine_name"] for m in meds] == ["Metformin"] and dropped == 5


def test_at_most_30_medicine_lines_are_taken():
    meds, _, _ = ps.validate_ai_response({"legibility": "good", "medicines": [{"name": f"Med{i}", "confidence": 0.9} for i in range(80)]})
    assert len(meds) == 30


# ---- end to end through the API (fake vision model) ----------------------------------------------
def test_new_details_are_returned_and_encrypted_at_rest(user_a):
    fake_ai(FULL_REPLY)
    p = upload(user_a, prescription_image(SAMPLE_LINES)).json()
    assert p["patient"]["name"] == "Asha Verma" and p["prescriber"]["registration_number"] == "KMC 12345"
    assert p["diagnosis"] == "Type 2 diabetes" and "Metformin" in p["full_transcription"] and p["ai_warnings"] == ["Bottom edge of the page is cut off"]
    it = [i for i in p["items"] if i["medicine_name"] == "Metformin"][0]
    assert it["raw_text"].startswith("Tab Metformin") and it["additional_instructions"] == "with warm water"
    assert p["doctor_name"] == "Dr. Meena Rao"
    with engine.connect() as c:  # no readable trace of the sensitive details in the database
        raw = " ".join(str(v) for t, col in (("prescriptions", "ocr_text"), ("prescription_items", "flags")) for row in c.execute(text(f"SELECT {col} FROM {t}")) for v in row)
    for secret in ("Asha Verma", "KMC 12345", "Type 2 diabetes", "with warm water", "SMX1"):
        assert secret not in raw


def test_status_clear_check_and_unclear(user_a):
    fake_ai({"legibility": "fair", "medicines": [
        {"name": "Metformin", "strength": "500mg", "dosage_instruction": "1-0-1 after food", "duration": "30 days", "confidence": 0.97, "unclear_fields": []},
        {"name": "Amlodipine", "strength": None, "dosage_instruction": "0-0-1", "confidence": 0.9, "unclear_fields": ["strength"]},
        {"name": "Telmi?", "strength": None, "dosage_instruction": None, "confidence": 0.3, "unclear_fields": ["name", "dosage_instruction"],
         "uncertainty_note": "Second word is smudged"},
    ]})
    by = {i["medicine_name"]: i for i in upload(user_a, prescription_image(SAMPLE_LINES)).json()["items"]}
    assert by["Amlodipine"]["verification_status"] == "check"
    assert by["Telmi?"]["verification_status"] == "unclear" and by["Telmi?"]["uncertainty_note"] == "Second word is smudged"
    assert "model_uncertainty_note" in by["Telmi?"]["flags"] and by["Telmi?"]["needs_review"] is True
    # "clear" is never produced by a model that merely claims high confidence: without OCR text to cross-check it stays "check"
    if not ocr.run_ocr(ocr.load_image(prescription_image(SAMPLE_LINES))).available:
        assert by["Metformin"]["verification_status"] == "check"
    else:
        assert by["Metformin"]["verification_status"] in ("clear", "check")


def test_status_rules_directly():
    v = ps.verification_status
    assert v("Metformin", "1-0-1", [], 0.95, False, False) == "clear"
    assert v("Metformin", "1-0-1", ["strength_not_found"], 0.95, True, False) == "check"
    assert v("Metformin", None, [], 0.95, False, False) == "check"  # no instruction written
    assert v("Metformin", "1-0-1", [], 0.7, False, False) == "check"
    assert v(None, "1-0-1", [], 0.95, False, False) == "unclear"
    assert v("Metformin", "1-0-1", [], 0.35, False, False) == "unclear"
    assert v("Metformin", "1-0-1", ["unclear:name"], 0.95, True, False) == "unclear"
    assert v("Metformin", None, ["unclear:dosage_instruction"], 0.9, True, False) == "unclear"
    assert v("Metformin", "1-0-1", ["unclear:name"], 0.3, False, True) == "clear"  # user typed/checked it


def test_unreadable_page_creates_nothing_and_invents_nothing(user_a):
    fake_ai({"legibility": "poor", "warnings": ["Page is out of focus"], "medicines": [{"name": None, "confidence": 0.1}]})
    p = upload(user_a, prescription_image([])).json()  # blank page: no local OCR lines either
    assert p["status"] == "failed" and p["items"] == [] and p["message"]
    assert "ai_lines_discarded_as_invalid" in p["warnings"] and "model_reports_poor_legibility" in p["warnings"]


@pytest.mark.parametrize("reply", ["this is not json at all", {"medicines": "none"}, [], {"legibility": "good"}])
def test_malformed_reply_falls_back_to_local_parser(user_a, reply):
    fake_ai(reply)
    p = upload(user_a, prescription_image(SAMPLE_LINES)).json()
    assert "ai_extraction_failed_used_local_parser" in p["warnings"]
    assert p["patient"] is None and p["full_transcription"] is None


def test_missing_fields_are_flagged_not_filled_in(user_a):
    fake_ai({"legibility": "good", "medicines": [{"name": "Telmisartan", "confidence": 0.9}]})
    it = upload(user_a, prescription_image(SAMPLE_LINES)).json()["items"][0]
    assert it["strength"] is None and it["dosage_instruction"] is None and it["frequency_text"] is None
    assert {"strength_not_found", "dosage_instruction_not_found"} <= set(it["flags"]) and it["verification_status"] != "clear"


def test_unrecognised_shorthand_is_flagged_and_kept_verbatim(user_a):
    fake_ai({"legibility": "good", "medicines": [
        {"name": "Metformin", "strength": "500mg", "dosage_instruction": "1-0-1 after food", "confidence": 0.9},
        {"name": "Cetirizine", "strength": "10mg", "dosage_instruction": "as dir. by Dr", "confidence": 0.9}]})
    by = {i["medicine_name"]: i for i in upload(user_a, prescription_image(SAMPLE_LINES)).json()["items"]}
    assert "instruction_not_recognised" in by["Cetirizine"]["flags"] and by["Cetirizine"]["dosage_instruction"] == "as dir. by Dr"
    assert "instruction_not_recognised" not in by["Metformin"]["flags"]


def test_image_sent_to_the_model_is_the_enhanced_upright_jpeg(user_a):
    seen = {}

    def handler(req):
        part = [p for p in json.loads(req.content)["contents"][0]["parts"] if "inlineData" in p][0]["inlineData"]
        seen["mime"] = part["mimeType"]
        import base64
        seen["img"] = Image.open(io.BytesIO(base64.b64decode(part["data"])))
        return gemini_text_response(FULL_REPLY)

    install_fake_gemini(handler)
    upload(user_a, prescription_image(SAMPLE_LINES))
    assert seen["mime"] == "image/jpeg" and seen["img"].format == "JPEG"


# ---- confirmation gate is untouched --------------------------------------------------------------
def test_reminders_only_after_explicit_confirmation_of_ai_output(user_a):
    fake_ai(FULL_REPLY)
    p = upload(user_a, prescription_image(SAMPLE_LINES)).json()
    item = [i for i in p["items"] if i["medicine_name"] == "Metformin"][0]
    assert user_a.get("/api/reminders/eligible").json() == []
    r = user_a.post("/api/reminders", json={"prescription_item_id": item["id"], "times": ["08:00"]})
    assert r.status_code == 409  # AI output alone never creates a reminder
    assert user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [item["id"]], "acknowledged": False}).status_code == 422
    assert user_a.post("/api/reminders", json={"prescription_item_id": item["id"], "times": ["08:00"]}).status_code == 409
    assert user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [item["id"]], "acknowledged": True}).status_code == 200
    assert user_a.post("/api/reminders", json={"prescription_item_id": item["id"], "times": ["08:00"]}).status_code == 201


def test_confirmed_prescription_stays_locked(user_a):
    fake_ai(FULL_REPLY)
    p = upload(user_a, prescription_image(SAMPLE_LINES)).json()
    item = p["items"][0]
    user_a.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [item["id"]], "acknowledged": True})
    r = user_a.put(f"/api/prescriptions/{p['id']}/items/{item['id']}", json={"medicine_name": "Changed", "dosage_instruction": "2-2-2"})
    assert r.status_code == 409


def test_editing_keeps_the_original_written_line_for_comparison(user_a):
    fake_ai(FULL_REPLY)
    p = upload(user_a, prescription_image(SAMPLE_LINES)).json()
    it = p["items"][0]
    after = user_a.put(f"/api/prescriptions/{p['id']}/items/{it['id']}", json={"medicine_name": "Metformin", "strength": "850mg", "dosage_instruction": "1-0-1 after food"}).json()
    e = after["items"][0]
    assert e["verification_status"] == "clear" and e["edited_by_user"] and e["raw_text"].startswith("Tab Metformin 500mg")


# ---- backward compatibility with records saved before the Analyzer -------------------------------
def test_old_format_records_still_load(user_a):
    with SessionLocal() as db:
        uid = db.query(User).first().id
        rx = Prescription(user_id=uid, status="extracted", extraction_engine="tesseract-rules", quality={"ok": True}, ocr_text="Tab Metformin 500mg 1-0-1\nplain old OCR text",
                          warnings=[], doctor_name="Dr Old")
        db.add(rx)
        db.flush()
        db.add(PrescriptionItem(prescription_id=rx.id, position=0, medicine_name="Metformin", strength="500mg", dosage_instruction="1-0-1",
                                confidence=0.9, needs_review=True, flags=["duration_not_found"]))  # old list-style flags
        db.commit()
        pid = rx.id
    got = user_a.get(f"/api/prescriptions/{pid}")
    assert got.status_code == 200
    body = got.json()
    it = body["items"][0]
    assert it["flags"] == ["duration_not_found"] and it["verification_status"] == "check" and it["raw_text"] is None
    assert body["patient"] is None and body["full_transcription"] is None
    assert any(r["id"] == pid for r in user_a.get("/api/prescriptions").json())


def test_pack_and_unpack_round_trip_both_formats():
    assert ps.unpack_flags(["a", "b"]) == (["a", "b"], {}) and ps.unpack_flags(None) == ([], {})
    packed = ps.pack_flags(["a"], {"raw_text": "x", "uncertainty_note": None})
    assert packed == {"flags": ["a"], "extra": {"raw_text": "x"}} and ps.unpack_flags(packed) == (["a"], {"raw_text": "x"})
    assert ps.pack_flags(["a"], {"raw_text": None}) == ["a"]  # nothing extra -> the old list format
    assert ps.unpack_text("just ocr text") == ("just ocr text", {}) and ps.unpack_text(None) == (None, {})
    env = ps.pack_text("ocr", {"patient": {"name": "A"}, "diagnosis": None})
    assert ps.unpack_text(env) == ("ocr", {"patient": {"name": "A"}})
    assert ps.pack_text("ocr", {"diagnosis": None}) == "ocr"
    assert ps.unpack_text("SMX1\n{broken json") == (None, {})  # damaged envelope must not crash the page


def test_other_users_cannot_see_the_new_details(user_a, make_client):
    fake_ai(FULL_REPLY)
    pid = upload(user_a, prescription_image(SAMPLE_LINES)).json()["id"]
    b = make_client("b@example.com")
    assert b.get(f"/api/prescriptions/{pid}").status_code == 404
