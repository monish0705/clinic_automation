from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.patient import Patient
from app.models.enums import MessageDirection
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.patient_repository import PatientRepository
from app.utils.validators import normalize_phone_number


class ConversationService:
    """Service handling multi-turn conversation sessions and message auditing."""

    @classmethod
    def get_or_create_session(
        cls,
        db: Session,
        phone: str,
        profile_name: Optional[str] = None
    ) -> Tuple[Conversation, Patient]:
        clean_phone = normalize_phone_number(phone)
        patient = PatientRepository.get_or_create(db, phone=clean_phone, name=profile_name)
        conv = ConversationRepository.get_or_create(db, patient_id=patient.id, phone=clean_phone)
        return conv, patient

    @classmethod
    def update_state(
        cls,
        db: Session,
        conv_id: int,
        state: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        return ConversationRepository.update_state(db, conv_id, state, metadata)

    @classmethod
    def reset_state(cls, db: Session, conv_id: int) -> Conversation:
        return ConversationRepository.reset_state(db, conv_id)

    @classmethod
    def is_duplicate_event(cls, db: Session, message_id: Optional[str]) -> bool:
        if not message_id:
            return False
        return ConversationRepository.is_message_duplicate(db, message_id)

    @classmethod
    def record_inbound(
        cls,
        db: Session,
        conv: Conversation,
        patient: Patient,
        text: str,
        message_id: Optional[str] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
    ):
        return ConversationRepository.log_message(
            db=db,
            conv_id=conv.id,
            patient_id=patient.id,
            direction=MessageDirection.INBOUND,
            content=text,
            message_id=message_id,
            raw_payload=raw_payload,
        )

    @classmethod
    def record_outbound(
        cls,
        db: Session,
        conv: Conversation,
        patient: Patient,
        text: str,
        message_id: Optional[str] = None,
    ):
        return ConversationRepository.log_message(
            db=db,
            conv_id=conv.id,
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            content=text,
            message_id=message_id,
        )
