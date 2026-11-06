from datetime import date as DateType, datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus


class DoctorRepository:
    """Repository handling doctor entities, schedules, and dynamic slot calculation."""

    DAY_MAP = {
        "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
        "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"
    }

    @staticmethod
    def get_by_id(db: Session, doctor_id: int) -> Optional[Doctor]:
        return db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.is_active.is_(True)).first()

    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Doctor]:
        name_clean = name.strip().lower()
        if name_clean.startswith("dr.") or name_clean.startswith("dr "):
            core_name = name_clean.replace("dr.", "").replace("dr ", "").strip()
        else:
            core_name = name_clean

        doctors = db.query(Doctor).filter(Doctor.is_active.is_(True)).all()
        for doc in doctors:
            if core_name in doc.name.lower():
                return doc
        return None

    @staticmethod
    def list_active(db: Session, clinic_id: Optional[int] = None) -> List[Doctor]:
        query = db.query(Doctor).filter(Doctor.is_active.is_(True))
        if clinic_id:
            query = query.filter(Doctor.clinic_id == clinic_id)
        return query.all()

    @classmethod
    def get_available_slots(cls, db: Session, doctor_id: int, target_date: DateType) -> List[str]:
        """Calculates free slots for a doctor on target_date by comparing schedule with active bookings."""
        doctor = cls.get_by_id(db, doctor_id)
        if not doctor:
            return []

        day_full = target_date.strftime("%A")
        day_abbr = cls.DAY_MAP.get(day_full, day_full[:3])

        # Find availability definition for this day
        avail = db.query(DoctorAvailability).filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.is_available.is_(True),
            DoctorAvailability.day_of_week.ilike(f"%{day_abbr}%")
        ).first()

        if not avail:
            return []

        all_slots = [s.strip() for s in avail.available_slots.split(",") if s.strip()]

        # Query booked slots on that date (excluding CANCELLED appointments)
        active_statuses = [AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]
        booked_records = db.query(Appointment.time_slot).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(active_statuses)
        ).all()

        booked_slots = {b[0] for b in booked_records}
        return [slot for slot in all_slots if slot not in booked_slots]
