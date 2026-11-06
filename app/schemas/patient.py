from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    phone: str = Field(..., description="E.164 normalized phone number e.g. +919876543210")
    name: Optional[str] = Field(None, description="Patient's full name")
    email: Optional[str] = Field(None, description="Patient's email address")


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class PatientResponse(PatientBase):
    id: int
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
