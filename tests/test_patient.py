from app.repositories.patient_repository import PatientRepository
from app.utils.validators import normalize_phone_number


def test_phone_normalization():
    assert normalize_phone_number("whatsapp:+919876543210") == "+919876543210"
    assert normalize_phone_number("  +91 98765-43210 ") == "+919876543210"
    assert normalize_phone_number("9876543210") == "+919876543210"


def test_patient_get_or_create(db):
    p1 = PatientRepository.get_or_create(db, "+919999911111", "Alice Smith")
    assert p1.id is not None
    assert p1.name == "Alice Smith"

    # Same phone should retrieve existing without creating duplicate
    p2 = PatientRepository.get_or_create(db, "+919999911111")
    assert p2.id == p1.id
    assert p2.name == "Alice Smith"


def test_patient_api_endpoints(client, admin_headers):
    # Create patient via public endpoint
    resp = client.post("/api/v1/patients", json={"phone": "+919888877777", "name": "Bob Jones"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["phone"] == "+919888877777"
    assert data["name"] == "Bob Jones"
    patient_id = data["id"]

    # Retrieve patient by ID (Admin authorized)
    get_resp = client.get(f"/api/v1/patients/{patient_id}", headers=admin_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Bob Jones"

    # List patients
    list_resp = client.get("/api/v1/patients", headers=admin_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1
