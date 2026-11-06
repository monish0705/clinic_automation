from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.enums import ReminderType, ReminderStatus


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_type = Column(SQLEnum(ReminderType), nullable=False)
    scheduled_for = Column(DateTime, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(ReminderStatus), default=ReminderStatus.PENDING, nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    error_message = Column(String(500), nullable=True)

    appointment = relationship("Appointment", back_populates="reminders")
