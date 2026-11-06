from app.core.security import verify_password, get_password_hash


def test_password_hashing():
    pwd = "SecureClinicPassword@2026"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_login_success(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "AdminPass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "ADMIN"


def test_login_failure(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "WrongPassword"})
    assert resp.status_code == 401


def test_unauthorized_endpoints(client):
    # Missing token
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_rbac_admin_vs_receptionist(client, admin_headers, receptionist_headers):
    # Endpoint: POST /api/v1/doctors requires ADMIN role
    new_doc_payload = {
        "clinic_id": 1,
        "name": "Dr. House",
        "speciality": "Diagnostics",
        "fee": 1000.0,
        "booking_type": "AUTO_CONFIRM",
        "is_active": True
    }

    # Receptionist attempts to create doctor -> Forbidden (403)
    resp_recep = client.post("/api/v1/doctors", json=new_doc_payload, headers=receptionist_headers)
    assert resp_recep.status_code == 403

    # Admin creates doctor -> Created (200)
    resp_admin = client.post("/api/v1/doctors", json=new_doc_payload, headers=admin_headers)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["name"] == "Dr. House"
