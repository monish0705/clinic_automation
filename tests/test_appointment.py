from datetime import datetime, timedelta
import pytest
from app.services.appointment_service import AppointmentService, DoubleBookingError, AppointmentServiceError
from app.repositories.doctor_repository import DoctorRepository
from app.models.enums import AppointmentStatus


def get_future_weekday(min_days_ahead: int = 1):
    """Returns a date at least min_days_ahead in the future that falls on a Monday-Friday."""
    d = datetime.utcnow().date() + timedelta(days=min_days_ahead)
    while d.weekday() in (5, 6):  # Avoid Sat/Sun for strict schedule safety
        d += timedelta(days=1)
    return d


def test_appointment_successful_booking(db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    target_date = get_future_weekday(1)

    appt = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919876543210",
        doctor_id=doc.id,
        appointment_date=target_date,
        time_slot="10:00",
        patient_name="John Doe"
    )

    assert appt.id is not None
    assert appt.appointment_code.startswith("APT-")
    assert appt.status == AppointmentStatus.CONFIRMED
    assert appt.time_slot == "10:00"


def test_appointment_invalid_past_date(db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    yesterday = datetime.utcnow().date() - timedelta(days=1)

    with pytest.raises(AppointmentServiceError):
        AppointmentService.book_appointment(
            db=db,
            patient_phone="+919876543210",
            doctor_id=doc.id,
            appointment_date=yesterday,
            time_slot="10:00"
        )


def test_double_booking_prevention(db):
    """
    CONCURRENCY TEST:
    Verifies that once a doctor slot is booked on a date,
    a second booking attempt for the identical slot raises DoubleBookingError.
    """
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    target_date = get_future_weekday(2)

    # First booking succeeds
    appt1 = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919111111111",
        doctor_id=doc.id,
        appointment_date=target_date,
        time_slot="09:00",
        patient_name="Patient One"
    )
    assert appt1.id is not None

    # Immediate second booking for the same slot must fail
    with pytest.raises(DoubleBookingError):
        AppointmentService.book_appointment(
            db=db,
            patient_phone="+919222222222",
            doctor_id=doc.id,
            appointment_date=target_date,
            time_slot="09:00",
            patient_name="Patient Two"
        )


def test_appointment_rescheduling(db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    day1 = get_future_weekday(1)
    day2 = get_future_weekday(3)

    appt = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919876543210",
        doctor_id=doc.id,
        appointment_date=day1,
        time_slot="10:00"
    )

    # Reschedule to day2 at 11:00
    rescheduled = AppointmentService.reschedule_appointment(
        db=db,
        appointment_code=appt.appointment_code,
        new_date=day2,
        new_time_slot="11:00",
        patient_phone="+919876543210"
    )

    assert rescheduled.appointment_date == day2
    assert rescheduled.time_slot == "11:00"
    assert rescheduled.status == AppointmentStatus.CONFIRMED

    # Ensure previous slot on day1 is now freed
    free_slots = AppointmentService.get_available_slots(db, doc.id, day1)
    assert "10:00" in free_slots


def test_appointment_cancellation(db):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    target_date = get_future_weekday(2)

    appt = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919876543210",
        doctor_id=doc.id,
        appointment_date=target_date,
        time_slot="14:00"
    )

    cancelled = AppointmentService.cancel_appointment(
        db=db,
        appointment_code=appt.appointment_code,
        patient_phone="+919876543210",
        reason="Patient requested"
    )
    assert cancelled.status == AppointmentStatus.CANCELLED

    # Check slot is freed up for other patients
    free_slots = AppointmentService.get_available_slots(db, doc.id, target_date)
    assert "14:00" in free_slots


def test_cross_patient_authorization_protection(db):
    """
    SECURITY TEST:
    A patient with phone B cannot cancel or reschedule an appointment belonging to patient A.
    """
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    target_date = get_future_weekday(2)

    appt = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919111111111",
        doctor_id=doc.id,
        appointment_date=target_date,
        time_slot="10:30"
    )

    with pytest.raises(PermissionError):
        AppointmentService.cancel_appointment(
            db=db,
            appointment_code=appt.appointment_code,
            patient_phone="+919999999999"  # Attacker's phone
        )
