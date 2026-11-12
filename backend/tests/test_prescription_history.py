"""Removing one saved prescription: only that prescription goes, with its own reminders and dose history.

The 'Do you want to remove this prescription?' dialog is built on GET /prescriptions/{id}/impact (read-only) and
DELETE /prescriptions/{id}. Cancelling the dialog never calls DELETE, so the tests below show that the impact preview
changes nothing and that deleting is limited to the one prescription the user chose.
"""
import os

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models import Prescription
from tests.helpers import prescription_image


def upload_blank(client):
    return client.post("/api/prescriptions", files={"file": ("rx.jpg", prescription_image([]), "image/jpeg")})


def make_rx(client, medicine="Metformin", confirm=True, remind=False):
    """Manual-entry prescription (works without OCR or AI). Optionally confirmed and with a reminder."""
    p = upload_blank(client).json()
    r = client.post(f"/api/prescriptions/{p['id']}/items", json={"medicine_name": medicine, "strength": "500mg", "dosage_instruction": "1-0-1 after food", "duration_text": "30 days"})
    assert r.status_code == 201
    item = r.json()["items"][0]
    if confirm:
        assert client.post(f"/api/prescriptions/{p['id']}/confirm", json={"item_ids": [item["id"]], "acknowledged": True}).status_code == 200
    rid = None
    if remind:
        rem = client.post("/api/reminders", json={"prescription_item_id": item["id"], "times": ["00:01", "23:58"]})
        assert rem.status_code == 201
        rid = rem.json()["id"]
    return p["id"], item["id"], rid


def take_due_doses(client):
    due = client.get("/api/reminders/due").json()
    client.get("/api/reminders/today")  # makes sure today's doses exist
    due = client.get("/api/reminders/due").json()
    for d in due:
        client.post(f"/api/reminders/doses/{d['id']}", json={"status": "taken"})
    return len(due)


def counts():
    with engine.connect() as c:
        return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("prescriptions", "prescription_items", "reminders", "dose_logs", "health_records")}


# ---- the preview ----------------------------------------------------------------------------------
def test_impact_describes_what_would_go_and_changes_nothing(user_a):
    pid, _, _ = make_rx(user_a, remind=True)
    taken = take_due_doses(user_a)
    before = counts()
    imp = user_a.get(f"/api/prescriptions/{pid}/impact")
    assert imp.status_code == 200
    body = imp.json()
    assert body["status"] == "confirmed" and body["medicines"] == 1 and body["reminders"] == 1 and body["active_reminders"] == 1
    assert body["in_timeline"] is True and body["doses_taken"] == taken and body["doses_logged"] >= taken
    assert counts() == before  # cancelling the dialog = this preview only; nothing was deleted
    assert user_a.get(f"/api/prescriptions/{pid}").status_code == 200


def test_impact_for_an_unconfirmed_prescription_has_no_reminders(user_a):
    pid, _, _ = make_rx(user_a, confirm=False)
    body = user_a.get(f"/api/prescriptions/{pid}/impact").json()
    assert body["status"] == "extracted" and body["reminders"] == 0 and body["doses_logged"] == 0 and body["in_timeline"] is False


def test_impact_and_delete_are_private(user_a, make_client):
    pid, _, _ = make_rx(user_a)
    b = make_client("b@example.com")
    assert b.get(f"/api/prescriptions/{pid}/impact").status_code == 404
    assert b.delete(f"/api/prescriptions/{pid}").status_code == 404
    assert user_a.get(f"/api/prescriptions/{pid}").status_code == 200  # still there


def test_impact_and_delete_for_unknown_id_are_404(user_a):
    assert user_a.get("/api/prescriptions/no-such-id/impact").status_code == 404
    assert user_a.delete("/api/prescriptions/no-such-id").status_code == 404


# ---- deleting exactly one -------------------------------------------------------------------------
def test_removing_one_prescription_leaves_the_others_untouched(user_a):
    keep_id, keep_item, keep_rem = make_rx(user_a, "Amlodipine", remind=True)
    gone_id, _, gone_rem = make_rx(user_a, "Metformin", remind=True)
    user_a.post("/api/records", json={"record_type": "visit", "title": "Check-up", "record_date": "2026-01-05", "details": "BP fine"})
    user_a.put("/api/profile", json={"allergies": ["penicillin"]})
    take_due_doses(user_a)
    before = counts()

    assert user_a.delete(f"/api/prescriptions/{gone_id}").status_code == 204

    ids = [p["id"] for p in user_a.get("/api/prescriptions").json()]
    assert ids == [keep_id]
    assert user_a.get(f"/api/prescriptions/{gone_id}").status_code == 404
    reminders = user_a.get("/api/reminders").json()
    assert [r["id"] for r in reminders] == [keep_rem] and gone_rem not in [r["id"] for r in reminders]
    after = counts()
    assert after["prescriptions"] == before["prescriptions"] - 1 and after["prescription_items"] == before["prescription_items"] - 1
    assert after["reminders"] == before["reminders"] - 1 and after["dose_logs"] < before["dose_logs"] and after["dose_logs"] > 0  # kept prescription's doses survive
    assert after["health_records"] == before["health_records"] == 1  # health records are not linked to prescriptions
    assert user_a.get("/api/profile").json()["allergies"] == ["penicillin"]
    assert [i["id"] for i in user_a.get(f"/api/prescriptions/{keep_id}").json()["items"]] == [keep_item]


def test_removed_prescription_leaves_the_timeline_but_records_stay(user_a):
    pid, _, _ = make_rx(user_a)
    user_a.post("/api/records", json={"record_type": "visit", "title": "Check-up", "record_date": "2026-01-05"})
    assert any(e["kind"] == "prescription" for e in user_a.get("/api/timeline").json())
    user_a.delete(f"/api/prescriptions/{pid}")
    assert [e["kind"] for e in user_a.get("/api/timeline").json()] == ["record"]  # the health record stays, the prescription entry is gone


def test_adherence_history_of_other_prescriptions_is_unchanged(user_a):
    _, _, _ = make_rx(user_a, "Amlodipine", remind=True)
    gone_id, _, _ = make_rx(user_a, "Metformin", remind=True)
    take_due_doses(user_a)
    before = user_a.get("/api/reminders/adherence?days=7").json()
    imp = user_a.get(f"/api/prescriptions/{gone_id}/impact").json()
    user_a.delete(f"/api/prescriptions/{gone_id}")
    after = user_a.get("/api/reminders/adherence?days=7").json()
    assert after["taken"] == before["taken"] - imp["doses_taken"]  # exactly the removed prescription's doses, nothing else


def test_removing_a_prescription_does_not_touch_another_users_data(user_a, make_client):
    b = make_client("b@example.com")
    b_id, _, b_rem = make_rx(b, remind=True)
    a_id, _, _ = make_rx(user_a, remind=True)
    user_a.delete(f"/api/prescriptions/{a_id}")
    assert [p["id"] for p in b.get("/api/prescriptions").json()] == [b_id]
    assert [r["id"] for r in b.get("/api/reminders").json()] == [b_rem]


def test_stored_photo_file_is_removed_with_its_prescription(client):
    from tests.conftest import register
    register(client, consents={"store_prescription_images": True})
    p = client.post("/api/prescriptions", files={"file": ("rx.jpg", prescription_image(["Tab Metformin 500mg 1-0-1"]), "image/jpeg")}).json()
    other = client.post("/api/prescriptions", files={"file": ("rx.jpg", prescription_image(["Tab Amlodipine 5mg 0-0-1"]), "image/jpeg")}).json()
    with SessionLocal() as db:
        mine, theirs = db.get(Prescription, p["id"]).image_path, db.get(Prescription, other["id"]).image_path
    assert os.path.exists(mine) and os.path.exists(theirs)
    assert client.get(f"/api/prescriptions/{p['id']}/impact").json()["has_photo"] is True
    assert client.delete(f"/api/prescriptions/{p['id']}").status_code == 204
    assert not os.path.exists(mine) and os.path.exists(theirs)  # only the chosen prescription's photo


def test_deleting_twice_is_a_clean_404(user_a):
    pid, _, _ = make_rx(user_a)
    assert user_a.delete(f"/api/prescriptions/{pid}").status_code == 204
    assert user_a.delete(f"/api/prescriptions/{pid}").status_code == 404
