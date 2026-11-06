from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.patient import Patient


class PatientRepository:
    """Repository handling patient entity lifecycle and lookups."""

    @staticmethod
    def get_by_id(db: Session, patient_id: int) -> Optional[Patient]:
        return db.query(Patient).filter(Patient.id == patient_id).first()

    @staticmethod
    def get_by_phone(db: Session, phone: str) -> Optional[Patient]:
        return db.query(Patient).filter(Patient.phone == phone).first()

    @staticmethod
    def get_or_create(db: Session, phone: str, name: Optional[str] = None) -> Patient:
        patient = db.query(Patient).filter(Patient.phone == phone).first()
        now = datetime.utcnow()
        if patient:
            patient.last_seen_at = now
            if name and not patient.name:
                patient.name = name
            db.commit()
            db.refresh(patient)
            return patient

        patient = Patient(phone=phone, name=name, last_seen_at=now)
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def update_name(db: Session, phone: str, name: str) -> Optional[Patient]:
        patient = db.query(Patient).filter(Patient.phone == phone).first()
        if patient:
            patient.name = name
            patient.last_seen_at = datetime.utcnow()
            db.commit()
            db.refresh(patient)
        return patient

    @staticmethod
    def list_patients(db: Session, skip: int = 0, limit: int = 50) -> List[Patient]:
        return db.query(Patient).order_by(Patient.last_seen_at.desc()).offset(skip).limit(limit).all()
