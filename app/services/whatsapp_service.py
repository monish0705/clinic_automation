from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.whatsapp.base import WhatsAppProvider
from app.services.whatsapp.cloud_api import MetaWhatsAppProvider
from app.services.whatsapp.twilio_provider import TwilioWhatsAppProvider
from app.services.whatsapp.mock_provider import MockWhatsAppProvider
from app.services.conversation_service import ConversationService
from app.agents.clinic_agent import ClinicAgent
from app.core.config import settings
from app.core.logging import logger

_active_provider: Optional[WhatsAppProvider] = None


def get_whatsapp_provider() -> WhatsAppProvider:
    """Factory creating or returning the configured WhatsApp messaging provider."""
    global _active_provider
    if _active_provider is None:
        provider_name = settings.WHATSAPP_PROVIDER.lower()
        if provider_name == "twilio":
            _active_provider = TwilioWhatsAppProvider()
        elif provider_name == "mock":
            _active_provider = MockWhatsAppProvider()
        else:
            _active_provider = MetaWhatsAppProvider()
    return _active_provider


def set_whatsapp_provider(provider: WhatsAppProvider):
    """Allows overriding active provider (e.g. for unit and integration testing)."""
    global _active_provider
    _active_provider = provider


class WhatsAppService:
    """Enterprise dispatch service coordinating providers, deduplication, and conversational agent."""

    @classmethod
    def send_message(cls, to_phone: str, message: str) -> Dict[str, Any]:
        provider = get_whatsapp_provider()
        return provider.send_text_message(to_phone, message)

    @classmethod
    def handle_incoming_webhook(
        cls,
        db: Session,
        raw_payload: Dict[str, Any],
        provider_type: str = "meta"
    ) -> Optional[str]:
        """
        Coordinates full inbound pipeline:
        1. Parsing normalized payload according to webhook format (Meta or Twilio)
        2. Webhook event deduplication (Idempotency)
        3. Agent routing & tool calling
        4. Outbound dispatch and audit logging
        """
        # Parse payload according to provider format
        if provider_type == "twilio":
            parser = TwilioWhatsAppProvider()
            parsed = parser.parse_incoming_webhook(raw_payload)
        else:
            parser = MetaWhatsAppProvider()
            parsed = parser.parse_incoming_webhook(raw_payload)

        # Fallback to active provider if neither matched
        if not parsed:
            active = get_whatsapp_provider()
            parsed = active.parse_incoming_webhook(raw_payload)

        if not parsed:
            logger.info("[WHATSAPP] Webhook contained no actionable text message (e.g. read receipt).")
            return None

        phone = parsed["from_phone"]
        text = parsed["text"]
        message_id = parsed["message_id"]
        profile_name = parsed.get("profile_name")

        # Deduplication check
        if message_id and ConversationService.is_duplicate_event(db, message_id):
            logger.warning(f"[WHATSAPP] Duplicate webhook event detected: {message_id}. Skipping processing.")
            return None

        if not text:
            return None

        # Execute Agent Logic
        reply_text = ClinicAgent.process_incoming_message(
            db=db,
            phone=phone,
            message_text=text,
            profile_name=profile_name,
            message_id=message_id,
        )

        # Dispatch Outbound Reply
        dispatch_result = cls.send_message(to_phone=phone, message=reply_text)
        out_msg_id = dispatch_result.get("message_id")

        # Record outbound message
        conv, patient = ConversationService.get_or_create_session(db, phone)
        ConversationService.record_outbound(
            db=db,
            conv=conv,
            patient=patient,
            text=reply_text,
            message_id=out_msg_id
        )

        return reply_text
