from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.patient import PatientResponse, PatientCreate, PatientUpdate
from app.models.patient import Patient
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.patient_repository import PatientRepository
from app.services.auth_service import require_roles
from app.utils.validators import normalize_phone_number

router = APIRouter(prefix="/api/v1/patients", tags=["Patients"])


@router.get("", response_model=List[PatientResponse], summary="List Patients (Staff Only)")
def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.RECEPTIONIST, UserRole.DOCTOR]))
):
    """Returns paginated list of clinic patients."""
    return PatientRepository.list_patients(db, skip=skip, limit=limit)


@router.get("/{patient_id}", response_model=PatientResponse, summary="Get Patient by ID")
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.RECEPTIONIST, UserRole.DOCTOR]))
):
    patient = PatientRepository.get_by_id(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


@router.post("", response_model=PatientResponse, summary="Register or Lookup Patient")
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db)
):
    clean_phone = normalize_phone_number(patient_in.phone)
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Invalid phone number format.")
    return PatientRepository.get_or_create(db, phone=clean_phone, name=patient_in.name)
