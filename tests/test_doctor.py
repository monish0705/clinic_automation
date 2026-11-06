from datetime import datetime, timedelta
from app.repositories.doctor_repository import DoctorRepository


def test_doctor_lookup_by_name(db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    assert doc is not None
    assert doc.speciality == "General Physician"

    doc_partial = DoctorRepository.get_by_name(db, "patel")
    assert doc_partial is not None
    assert doc_partial.name == "Dr. Patel"

    doc_none = DoctorRepository.get_by_name(db, "Dr. NonExistent")
    assert doc_none is None


def test_doctor_availability_slots(db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    # Find next Monday
    today = datetime.utcnow().date()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_monday = today + timedelta(days=days_ahead)

    slots = DoctorRepository.get_available_slots(db, doc.id, next_monday)
    assert len(slots) > 0
    assert "09:00" in slots
    assert "10:00" in slots


def test_doctor_api_availability(client, db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    date_str = tomorrow.strftime("%Y-%m-%d")

    resp = client.get(f"/api/v1/doctors/{doc.id}/availability?date={date_str}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["doctor_id"] == doc.id
    assert "available_slots" in data
