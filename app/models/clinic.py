from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.orm import relationship
from app.database.base import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    address = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    timings = Column(String(255), nullable=False)
    fees_summary = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    doctors = relationship("Doctor", back_populates="clinic", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="clinic")
