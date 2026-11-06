from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.models.enums import MessageDirection


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    message_id = Column(String(120), unique=True, index=True, nullable=True)  # WhatsApp WAMID / Twilio SID
    content = Column(Text, nullable=False)
    raw_payload = Column(JSON, default=dict, nullable=True)
    status = Column(String(50), default="sent", nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
