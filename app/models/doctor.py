from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.enums import BookingType


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    speciality = Column(String(100), nullable=False, index=True)
    email = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)
    fee = Column(Float, default=500.0, nullable=False)
    booking_type = Column(SQLEnum(BookingType), default=BookingType.AUTO_CONFIRM, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    clinic = relationship("Clinic", back_populates="doctors")
    availabilities = relationship("DoctorAvailability", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor")
