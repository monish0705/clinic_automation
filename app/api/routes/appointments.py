from datetime import date as DateType
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.appointment import (
    AppointmentResponse,
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentCancel
)
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, UserRole
from app.models.user import User
from app.services.appointment_service import (
    AppointmentService,
    DoubleBookingError,
    AppointmentNotFoundError,
    AppointmentServiceError
)
from app.repositories.appointment_repository import AppointmentRepository
from app.services.auth_service import require_roles

router = APIRouter(prefix="/api/v1/appointments", tags=["Appointments"])


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED, summary="Book an Appointment")
def create_appointment(
    appt_in: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """
    Atomically books an appointment.
    Guarantees concurrency safety against double booking and handles idempotency.
    """
    try:
        appointment = AppointmentService.book_appointment(
            db=db,
            patient_phone=appt_in.patient_phone,
            doctor_id=appt_in.doctor_id,
            appointment_date=appt_in.appointment_date,
            time_slot=appt_in.time_slot,
            patient_name=appt_in.patient_name,
            notes=appt_in.notes,
            idempotency_key=appt_in.idempotency_key,
        )
        return appointment
    except DoubleBookingError as dbe:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(dbe))
    except (AppointmentServiceError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("", response_model=List[AppointmentResponse], summary="List Appointments (Staff Only)")
def list_appointments(
    doctor_id: Optional[int] = None,
    appointment_date: Optional[DateType] = None,
    status_filter: Optional[AppointmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.RECEPTIONIST, UserRole.DOCTOR]))
):
    """Lists appointments with optional filters for doctor, date, and status."""
    query = db.query(Appointment)
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if appointment_date:
        query = query.filter(Appointment.appointment_date == appointment_date)
    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    return query.order_by(Appointment.appointment_date.desc(), Appointment.time_slot.asc()).offset(skip).limit(limit).all()


@router.get("/{appointment_code}", response_model=AppointmentResponse, summary="Get Appointment by Code")
def get_appointment(appointment_code: str, db: Session = Depends(get_db)):
    appt = AppointmentRepository.get_by_code(db, appointment_code)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return appt


@router.patch("/{appointment_code}/reschedule", response_model=AppointmentResponse, summary="Reschedule Appointment")
def reschedule_appointment(
    appointment_code: str,
    reschedule_in: AppointmentReschedule,
    db: Session = Depends(get_db)
):
    """Atomically reschedules an appointment to a new date and time slot."""
    try:
        updated = AppointmentService.reschedule_appointment(
            db=db,
            appointment_code=appointment_code,
            new_date=reschedule_in.new_date,
            new_time_slot=reschedule_in.new_time_slot,
        )
        return updated
    except AppointmentNotFoundError:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    except DoubleBookingError as dbe:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(dbe))
    except (AppointmentServiceError, PermissionError) as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.delete("/{appointment_code}", response_model=AppointmentResponse, summary="Cancel Appointment")
def cancel_appointment(
    appointment_code: str,
    cancel_in: Optional[AppointmentCancel] = None,
    db: Session = Depends(get_db)
):
    """Cancels an existing appointment."""
    try:
        cancelled = AppointmentService.cancel_appointment(
            db=db,
            appointment_code=appointment_code,
            reason=cancel_in.reason if cancel_in else None
        )
        return cancelled
    except AppointmentNotFoundError:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
