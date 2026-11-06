import os
import pytest

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-purposes-minimum-32"
os.environ["WHATSAPP_PROVIDER"] = "mock"
os.environ["META_WA_APP_SECRET"] = "test_meta_secret"
os.environ["META_WA_VERIFY_TOKEN"] = "test_verify_token"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Clinic, Doctor, DoctorAvailability, User, UserRole, BookingType
from app.core.security import get_password_hash, create_access_token
from app.services.whatsapp_service import set_whatsapp_provider
from app.services.whatsapp.mock_provider import MockWhatsAppProvider

# Test Database Engine (in-memory SQLite shared across test session)
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def mock_wa():
    provider = MockWhatsAppProvider()
    set_whatsapp_provider(provider)
    yield provider
    provider.clear()


@pytest.fixture
def db(mock_wa):
    session = TestingSessionLocal()
    # Clean tables between tests
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()

    # Seed baseline test data
    clinic = Clinic(
        name="Test City Clinic",
        address="456 Test Street, Bangalore",
        phone="+919876543210",
        timings="Mon-Sat 9AM-8PM",
        fees_summary="₹500 General | ₹800 Specialist",
        is_active=True
    )
    session.add(clinic)
    session.commit()
    session.refresh(clinic)

    doc1 = Doctor(
        clinic_id=clinic.id,
        name="Dr. Sharma",
        speciality="General Physician",
        fee=500.0,
        booking_type=BookingType.AUTO_CONFIRM,
        is_active=True
    )
    doc2 = Doctor(
        clinic_id=clinic.id,
        name="Dr. Patel",
        speciality="Cardiologist",
        fee=800.0,
        booking_type=BookingType.MANUAL_APPROVAL,
        is_active=True
    )
    session.add_all([doc1, doc2])
    session.commit()
    session.refresh(doc1)
    session.refresh(doc2)

    avail1 = DoctorAvailability(
        doctor_id=doc1.id,
        day_of_week="Mon,Tue,Wed,Thu,Fri,Sat",
        available_slots="09:00,09:30,10:00,10:30,11:00,14:00,14:30,15:00",
        is_available=True
    )
    avail2 = DoctorAvailability(
        doctor_id=doc2.id,
        day_of_week="Mon,Wed,Fri",
        available_slots="10:00,11:00,12:00,15:00",
        is_available=True
    )
    session.add_all([avail1, avail2])

    admin = User(
        username="admin_test",
        email="admin@test.com",
        hashed_password=get_password_hash("AdminPass123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    receptionist = User(
        username="recep_test",
        email="recep@test.com",
        hashed_password=get_password_hash("RecepPass123"),
        role=UserRole.RECEPTIONIST,
        is_active=True
    )
    session.add_all([admin, receptionist])
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    token = create_access_token(data={"sub": "admin_test", "role": "ADMIN"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def receptionist_headers():
    token = create_access_token(data={"sub": "recep_test", "role": "RECEPTIONIST"})
    return {"Authorization": f"Bearer {token}"}
