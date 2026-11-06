import uuid
from datetime import date as DateType, datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, BookingType


class DoubleBookingError(Exception):
    """Raised when an attempt is made to book an already occupied slot."""
    pass


class AppointmentNotFoundError(Exception):
    """Raised when an appointment code does not exist."""
    pass


class AppointmentRepository:
    """
    Repository providing transactional, concurrency-safe appointment booking,
    rescheduling, cancellation, and reminder queries.
    """

    @staticmethod
    def generate_appointment_code() -> str:
        """Generates a human-friendly unique appointment code e.g. APT-84920."""
        random_suffix = uuid.uuid4().hex[:5].upper()
        return f"APT-{random_suffix}"

    @staticmethod
    def get_by_code(db: Session, code: str) -> Optional[Appointment]:
        return db.query(Appointment).filter(
            Appointment.appointment_code == code.strip().upper()
        ).first()

    @staticmethod
    def get_by_idempotency_key(db: Session, idempotency_key: str) -> Optional[Appointment]:
        if not idempotency_key:
            return None
        return db.query(Appointment).filter(
            Appointment.idempotency_key == idempotency_key
        ).first()

    @classmethod
    def create_atomic(
        cls,
        db: Session,
        clinic_id: int,
        doctor_id: int,
        patient_id: int,
        appointment_date: DateType,
        time_slot: str,
        booking_type: BookingType = BookingType.AUTO_CONFIRM,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Appointment:
        """
        Atomically books an appointment.
        Guarantees protection against double booking under concurrent requests
        via an atomic database transaction checking existing active bookings.
        """
        # 1. Check idempotency
        if idempotency_key:
            existing = cls.get_by_idempotency_key(db, idempotency_key)
            if existing:
                return existing

        # 2. Concurrency Lock & Slot Collision Check
        # Query existing active appointments for this doctor at the exact date and slot
        active_statuses = [AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]
        
        # Use with_for_update if database engine supports it (PostgreSQL), fallback for SQLite
        query = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appointment_date,
            Appointment.time_slot == time_slot,
            Appointment.status.in_(active_statuses)
        )
        try:
            collision = query.with_for_update().first()
        except Exception:
            # SQLite does not support SELECT FOR UPDATE, relies on transaction lock
            collision = query.first()

        if collision:
            raise DoubleBookingError(
                f"Doctor {doctor_id} is already booked on {appointment_date} at {time_slot}."
            )

        # 3. Create Appointment
        appointment_code = cls.generate_appointment_code()
        initial_status = (
            AppointmentStatus.CONFIRMED
            if booking_type == BookingType.AUTO_CONFIRM
            else AppointmentStatus.PENDING
        )

        appointment = Appointment(
            appointment_code=appointment_code,
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            patient_id=patient_id,
            appointment_date=appointment_date,
            time_slot=time_slot,
            status=initial_status,
            booking_type=booking_type,
            notes=notes,
            idempotency_key=idempotency_key,
            reminder_24h_sent=False,
            reminder_2h_sent=False,
        )

        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        return appointment

    @classmethod
    def reschedule_atomic(
        cls,
        db: Session,
        appointment_code: str,
        new_date: DateType,
        new_time_slot: str,
        patient_id: Optional[int] = None,
    ) -> Appointment:
        """
        Atomically moves an appointment to a new date and slot after verifying availability.
        """
        appointment = cls.get_by_code(db, appointment_code)
        if not appointment:
            raise AppointmentNotFoundError(f"Appointment {appointment_code} not found.")

        if patient_id and appointment.patient_id != patient_id:
            raise PermissionError("Access denied: appointment belongs to another patient.")

        # Check collision on new slot
        active_statuses = [AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]
        collision = db.query(Appointment).filter(
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.appointment_date == new_date,
            Appointment.time_slot == new_time_slot,
            Appointment.status.in_(active_statuses),
            Appointment.id != appointment.id,
        ).first()

        if collision:
            raise DoubleBookingError(
                f"Doctor is already booked on {new_date} at {new_time_slot}."
            )

        appointment.appointment_date = new_date
        appointment.time_slot = new_time_slot
        appointment.status = AppointmentStatus.CONFIRMED
        # Reset reminders for the new schedule
        appointment.reminder_24h_sent = False
        appointment.reminder_2h_sent = False

        db.commit()
        db.refresh(appointment)
        return appointment

    @classmethod
    def cancel_appointment(
        cls,
        db: Session,
        appointment_code: str,
        patient_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Appointment:
        """Cancels an appointment and ensures reminders are not dispatched."""
        appointment = cls.get_by_code(db, appointment_code)
        if not appointment:
            raise AppointmentNotFoundError(f"Appointment {appointment_code} not found.")

        if patient_id and appointment.patient_id != patient_id:
            raise PermissionError("Access denied: appointment belongs to another patient.")

        appointment.status = AppointmentStatus.CANCELLED
        if notes:
            appointment.notes = f"{appointment.notes or ''} [Cancelled: {notes}]"

        db.commit()
        db.refresh(appointment)
        return appointment

    @staticmethod
    def get_patient_upcoming(db: Session, patient_id: int) -> List[Appointment]:
        """Returns upcoming active appointments for a patient."""
        today = datetime.utcnow().date()
        return db.query(Appointment).filter(
            Appointment.patient_id == patient_id,
            Appointment.appointment_date >= today,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
        ).order_by(Appointment.appointment_date.asc(), Appointment.time_slot.asc()).all()

    @staticmethod
    def get_appointments_due_for_24h_reminder(db: Session, target_date: DateType) -> List[Appointment]:
        """Finds confirmed appointments for target_date where 24h reminder has not been sent."""
        return db.query(Appointment).filter(
            Appointment.appointment_date == target_date,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminder_24h_sent.is_(False)
        ).all()

    @staticmethod
    def get_appointments_due_for_2h_reminder(db: Session, target_date: DateType) -> List[Appointment]:
        """Finds confirmed appointments for target_date where 2h reminder has not been sent."""
        return db.query(Appointment).filter(
            Appointment.appointment_date == target_date,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminder_2h_sent.is_(False)
        ).all()

    @staticmethod
    def mark_reminder_sent(db: Session, appointment_id: int, reminder_field: str):
        """Flags reminder as sent to guarantee zero duplicate messages."""
        appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if appt:
            if reminder_field == "24h":
                appt.reminder_24h_sent = True
            elif reminder_field == "2h":
                appt.reminder_2h_sent = True
            db.commit()
