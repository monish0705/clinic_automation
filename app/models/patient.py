from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=True)
    email = Column(String(150), nullable=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointments = relationship("Appointment", back_populates="patient")
    conversations = relationship("Conversation", back_populates="patient")
