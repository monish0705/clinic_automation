from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base


class DoctorAvailability(Base):
    __tablename__ = "doctor_availabilities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(String(20), nullable=False)  # "Mon", "Tue", "Wed", etc.
    available_slots = Column(String(500), nullable=False)  # Comma-separated slots e.g. "09:00,09:30,10:00"
    is_available = Column(Boolean, default=True, nullable=False)

    doctor = relationship("Doctor", back_populates="availabilities")
