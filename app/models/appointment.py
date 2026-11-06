from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.enums import AppointmentStatus, BookingType


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_code = Column(String(32), unique=True, index=True, nullable=False)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_date = Column(Date, nullable=False, index=True)
    time_slot = Column(String(10), nullable=False, index=True)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.CONFIRMED, nullable=False, index=True)
    booking_type = Column(SQLEnum(BookingType), default=BookingType.AUTO_CONFIRM, nullable=False)
    notes = Column(String(500), nullable=True)

    # Reminders
    reminder_24h_sent = Column(Boolean, default=False, nullable=False)
    reminder_2h_sent = Column(Boolean, default=False, nullable=False)

    # Concurrency and Idempotency key
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)

    # Relationships
    clinic = relationship("Clinic", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    reminders = relationship("ReminderLog", back_populates="appointment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_doctor_date_slot", "doctor_id", "appointment_date", "time_slot"),
    )
