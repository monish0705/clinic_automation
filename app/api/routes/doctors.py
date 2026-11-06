from datetime import date as DateType, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.doctor import DoctorResponse, DoctorCreate, DoctorAvailabilityResponse
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.doctor_repository import DoctorRepository
from app.services.appointment_service import AppointmentService
from app.services.auth_service import require_roles
from app.utils.validators import parse_target_date

router = APIRouter(prefix="/api/v1/doctors", tags=["Doctors & Schedules"])


@router.get("", response_model=List[DoctorResponse], summary="List Active Doctors")
def list_doctors(clinic_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Retrieves all active clinic doctors."""
    return DoctorRepository.list_active(db, clinic_id)


@router.get("/{doctor_id}", response_model=DoctorResponse, summary="Get Doctor Profile")
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doc = DoctorRepository.get_by_id(db, doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found.")
    return doc


@router.get("/{doctor_id}/availability", response_model=DoctorAvailabilityResponse, summary="Get Available Time Slots")
def get_doctor_availability(
    doctor_id: int,
    date: str = Query(..., description="Target date in YYYY-MM-DD format e.g. 2026-11-10"),
    db: Session = Depends(get_db)
):
    """Calculates real-time free consultation slots for a doctor on a specific date."""
    doc = DoctorRepository.get_by_id(db, doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found.")

    target_date = parse_target_date(date)
    if not target_date:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    slots = AppointmentService.get_available_slots(db, doctor_id, target_date)
    return DoctorAvailabilityResponse(
        doctor_id=doc.id,
        doctor_name=doc.name,
        target_date=target_date.strftime("%Y-%m-%d"),
        available_slots=slots
    )


@router.post("", response_model=DoctorResponse, summary="Add New Doctor (Admin Only)")
def create_doctor(
    doc_in: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
):
    doc = Doctor(
        clinic_id=doc_in.clinic_id,
        name=doc_in.name,
        speciality=doc_in.speciality,
        email=doc_in.email,
        phone=doc_in.phone,
        fee=doc_in.fee,
        booking_type=doc_in.booking_type,
        is_active=doc_in.is_active
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc
