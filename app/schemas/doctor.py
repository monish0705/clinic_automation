from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import BookingType


class DoctorBase(BaseModel):
    name: str = Field(..., description="Doctor's full name e.g. Dr. Sharma")
    speciality: str = Field(..., description="Medical speciality e.g. Cardiologist")
    email: Optional[str] = None
    phone: Optional[str] = None
    fee: float = Field(default=500.0, description="Consultation fee in INR")
    booking_type: BookingType = BookingType.AUTO_CONFIRM
    is_active: bool = True


class DoctorCreate(DoctorBase):
    clinic_id: int


class DoctorResponse(DoctorBase):
    id: int
    clinic_id: int

    model_config = ConfigDict(from_attributes=True)


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    target_date: str
    available_slots: List[str]
