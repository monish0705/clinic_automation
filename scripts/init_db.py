import sys
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.models import Clinic, Doctor, DoctorAvailability, User, UserRole, BookingType
from app.core.security import get_password_hash
from app.core.config import settings


def init_and_seed_db():
    print("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

    db = SessionLocal()
    try:
        # 1. Seed Clinic
        clinic = db.query(Clinic).first()
        if not clinic:
            clinic = Clinic(
                name=settings.CLINIC_NAME,
                address=settings.CLINIC_ADDRESS,
                phone=settings.CLINIC_PHONE,
                timings=settings.CLINIC_TIMINGS,
                fees_summary=settings.CLINIC_FEES_SUMMARY,
                is_active=True,
            )
            db.add(clinic)
            db.commit()
            db.refresh(clinic)
            print(f"Created clinic: {clinic.name} (ID: {clinic.id})")

        # 2. Seed Doctors & Availabilities
        doctors_data = [
            {
                "name": "Dr. Sharma",
                "speciality": "General Physician",
                "email": "sharma@citycareclinic.com",
                "fee": 500.0,
                "booking_type": BookingType.AUTO_CONFIRM,
                "days": "Mon,Tue,Wed,Thu,Fri,Sat",
                "slots": "09:00,09:30,10:00,10:30,11:00,11:30,14:00,14:30,15:00,15:30",
            },
            {
                "name": "Dr. Patel",
                "speciality": "Cardiologist",
                "email": "patel@citycareclinic.com",
                "fee": 800.0,
                "booking_type": BookingType.MANUAL_APPROVAL,
                "days": "Mon,Wed,Fri",
                "slots": "10:00,11:00,12:00,15:00,16:00",
            },
            {
                "name": "Dr. Rao",
                "speciality": "Dermatologist",
                "email": "rao@citycareclinic.com",
                "fee": 700.0,
                "booking_type": BookingType.AUTO_CONFIRM,
                "days": "Tue,Thu,Sat",
                "slots": "09:00,10:00,11:00,14:00,15:00,16:00",
            },
        ]

        for doc_info in doctors_data:
            existing_doc = db.query(Doctor).filter(Doctor.name == doc_info["name"]).first()
            if not existing_doc:
                doc = Doctor(
                    clinic_id=clinic.id,
                    name=doc_info["name"],
                    speciality=doc_info["speciality"],
                    email=doc_info["email"],
                    fee=doc_info["fee"],
                    booking_type=doc_info["booking_type"],
                    is_active=True,
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)

                avail = DoctorAvailability(
                    doctor_id=doc.id,
                    day_of_week=doc_info["days"],
                    available_slots=doc_info["slots"],
                    is_available=True,
                )
                db.add(avail)
                db.commit()
                print(f"Created doctor: {doc.name} with schedule ({doc_info['days']})")

        # 3. Seed Default Admin User
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@citycareclinic.com",
                hashed_password=get_password_hash("Admin@12345"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            print("Created default admin user: 'admin' (password: Admin@12345)")

        print("Database initialization and seeding complete.")

    finally:
        db.close()


if __name__ == "__main__":
    init_and_seed_db()
