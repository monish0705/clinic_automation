from datetime import date as DateType, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import AppointmentStatus, BookingType


class AppointmentBase(BaseModel):
    doctor_id: int = Field(..., description="Doctor ID")
    appointment_date: DateType = Field(..., description="Target appointment date (YYYY-MM-DD)")
    time_slot: str = Field(..., description="Selected time slot (e.g. '10:00')")
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    patient_phone: str = Field(..., description="Patient phone number")
    patient_name: Optional[str] = Field(None, description="Patient full name")
    idempotency_key: Optional[str] = None


class AppointmentReschedule(BaseModel):
    new_date: DateType = Field(..., description="New appointment date (YYYY-MM-DD)")
    new_time_slot: str = Field(..., description="New time slot (e.g. '11:00')")


class AppointmentCancel(BaseModel):
    reason: Optional[str] = Field(None, description="Cancellation reason")


class AppointmentResponse(BaseModel):
    id: int
    appointment_code: str
    clinic_id: int
    doctor_id: int
    patient_id: int
    appointment_date: DateType
    time_slot: str
    status: AppointmentStatus
    booking_type: BookingType
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
