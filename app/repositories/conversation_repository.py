from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.enums import MessageDirection


class ConversationRepository:
    """Repository handling WhatsApp conversation sessions and message audit logging."""

    @staticmethod
    def get_or_create(db: Session, patient_id: int, phone: str) -> Conversation:
        conv = db.query(Conversation).filter(Conversation.phone == phone).first()
        now = datetime.utcnow()
        if conv:
            conv.last_interaction_at = now
            db.commit()
            db.refresh(conv)
            return conv

        conv = Conversation(
            patient_id=patient_id,
            phone=phone,
            current_state="IDLE",
            state_metadata={},
            last_interaction_at=now,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def update_state(
        db: Session,
        conv_id: int,
        state: str,
        state_metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            conv.current_state = state
            if state_metadata is not None:
                # Merge or replace metadata
                updated_meta = dict(conv.state_metadata or {})
                updated_meta.update(state_metadata)
                conv.state_metadata = updated_meta
            conv.last_interaction_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)
        return conv

    @staticmethod
    def reset_state(db: Session, conv_id: int) -> Conversation:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            conv.current_state = "IDLE"
            conv.state_metadata = {}
            conv.last_interaction_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)
        return conv

    @staticmethod
    def is_message_duplicate(db: Session, message_id: str) -> bool:
        """Checks if a webhook message has already been processed to prevent duplicates."""
        if not message_id:
            return False
        return db.query(Message).filter(Message.message_id == message_id).first() is not None

    @staticmethod
    def log_message(
        db: Session,
        conv_id: int,
        patient_id: int,
        direction: MessageDirection,
        content: str,
        message_id: Optional[str] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conv_id,
            patient_id=patient_id,
            direction=direction,
            content=content,
            message_id=message_id,
            raw_payload=raw_payload or {},
            status="delivered" if direction == MessageDirection.OUTBOUND else "received"
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_recent_messages(db: Session, conv_id: int, limit: int = 10) -> List[Message]:
        return db.query(Message).filter(
            Message.conversation_id == conv_id
        ).order_by(Message.created_at.desc()).limit(limit).all()
