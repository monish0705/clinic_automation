from datetime import date as DateType, datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.clinic import Clinic
from app.models.enums import AppointmentStatus, BookingType
from app.repositories.appointment_repository import (
    AppointmentRepository,
    DoubleBookingError,
    AppointmentNotFoundError
)
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.utils.validators import normalize_phone_number, normalize_time_slot
from app.core.config import settings


class AppointmentServiceError(Exception):
    pass


class AppointmentService:
    """Core domain business service orchestrating appointments and clinic operations."""

    @classmethod
    def get_clinic_info(cls, db: Session) -> Dict[str, Any]:
        clinic = db.query(Clinic).filter(Clinic.is_active.is_(True)).first()
        if clinic:
            return {
                "name": clinic.name,
                "address": clinic.address,
                "phone": clinic.phone,
                "timings": clinic.timings,
                "fees_summary": clinic.fees_summary,
            }
        return {
            "name": settings.CLINIC_NAME,
            "address": settings.CLINIC_ADDRESS,
            "phone": settings.CLINIC_PHONE,
            "timings": settings.CLINIC_TIMINGS,
            "fees_summary": settings.CLINIC_FEES_SUMMARY,
        }

    @classmethod
    def get_available_doctors(cls, db: Session) -> List[Doctor]:
        return DoctorRepository.list_active(db)

    @classmethod
    def get_available_slots(cls, db: Session, doctor_id: int, target_date: DateType) -> List[str]:
        # Validate date is not in the past
        today = datetime.utcnow().date()
        if target_date < today:
            return []
        return DoctorRepository.get_available_slots(db, doctor_id, target_date)

    @classmethod
    def book_appointment(
        cls,
        db: Session,
        patient_phone: str,
        doctor_id: int,
        appointment_date: DateType,
        time_slot: str,
        patient_name: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Appointment:
        """
        Validates business constraints and atomically books an appointment.
        """
        # 1. Normalize phone & fetch/create patient
        clean_phone = normalize_phone_number(patient_phone)
        if not clean_phone:
            raise AppointmentServiceError("A valid patient phone number is required.")

        patient = PatientRepository.get_or_create(db, phone=clean_phone, name=patient_name)

        # 2. Verify Doctor
        doctor = DoctorRepository.get_by_id(db, doctor_id)
        if not doctor:
            raise AppointmentServiceError(f"Doctor with ID {doctor_id} not found.")

        # 3. Validate Date (No past appointments)
        today = datetime.utcnow().date()
        if appointment_date < today:
            raise AppointmentServiceError(f"Cannot book appointment on a past date: {appointment_date}")

        # 4. Normalize Time Slot
        norm_slot = normalize_time_slot(time_slot)
        if not norm_slot:
            raise AppointmentServiceError(f"Invalid time format: {time_slot}")

        # 5. Check if slot is available according to doctor's schedule
        available_slots = cls.get_available_slots(db, doctor_id, appointment_date)
        if norm_slot not in available_slots:
            raise DoubleBookingError(
                f"Time slot {norm_slot} is not available for {doctor.name} on {appointment_date}."
            )

        # 6. Execute atomic booking in repository
        clinic = db.query(Clinic).filter(Clinic.is_active.is_(True)).first()
        clinic_id = clinic.id if clinic else doctor.clinic_id

        appointment = AppointmentRepository.create_atomic(
            db=db,
            clinic_id=clinic_id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            appointment_date=appointment_date,
            time_slot=norm_slot,
            booking_type=doctor.booking_type,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        return appointment

    @classmethod
    def reschedule_appointment(
        cls,
        db: Session,
        appointment_code: str,
        new_date: DateType,
        new_time_slot: str,
        patient_phone: Optional[str] = None,
    ) -> Appointment:
        """Reschedules an appointment with security verification of patient ownership."""
        appointment = AppointmentRepository.get_by_code(db, appointment_code)
        if not appointment:
            raise AppointmentNotFoundError(f"Appointment {appointment_code} not found.")

        # Security check: if phone is passed, verify patient owns this appointment
        if patient_phone:
            clean_phone = normalize_phone_number(patient_phone)
            patient = PatientRepository.get_by_phone(db, clean_phone)
            if not patient or appointment.patient_id != patient.id:
                raise PermissionError("Access denied: You can only reschedule your own appointments.")

        today = datetime.utcnow().date()
        if new_date < today:
            raise AppointmentServiceError("Cannot reschedule to a past date.")

        norm_slot = normalize_time_slot(new_time_slot)
        if not norm_slot:
            raise AppointmentServiceError(f"Invalid time slot: {new_time_slot}")

        available_slots = cls.get_available_slots(db, appointment.doctor_id, new_date)
        if norm_slot not in available_slots:
            raise DoubleBookingError(f"Time slot {norm_slot} is not available on {new_date}.")

        return AppointmentRepository.reschedule_atomic(
            db=db,
            appointment_code=appointment_code,
            new_date=new_date,
            new_time_slot=norm_slot,
            patient_id=appointment.patient_id
        )

    @classmethod
    def cancel_appointment(
        cls,
        db: Session,
        appointment_code: str,
        patient_phone: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Appointment:
        """Cancels an appointment with security verification of patient ownership."""
        appointment = AppointmentRepository.get_by_code(db, appointment_code)
        if not appointment:
            raise AppointmentNotFoundError(f"Appointment {appointment_code} not found.")

        if patient_phone:
            clean_phone = normalize_phone_number(patient_phone)
            patient = PatientRepository.get_by_phone(db, clean_phone)
            if not patient or appointment.patient_id != patient.id:
                raise PermissionError("Access denied: You can only cancel your own appointments.")

        return AppointmentRepository.cancel_appointment(
            db=db,
            appointment_code=appointment_code,
            patient_id=appointment.patient_id,
            notes=reason
        )

    @classmethod
    def get_patient_appointments(cls, db: Session, patient_phone: str) -> List[Appointment]:
        clean_phone = normalize_phone_number(patient_phone)
        patient = PatientRepository.get_by_phone(db, clean_phone)
        if not patient:
            return []
        return AppointmentRepository.get_patient_upcoming(db, patient.id)
