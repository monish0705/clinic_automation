from typing import Dict, Any, List, Optional
from app.services.whatsapp.base import WhatsAppProvider
from app.utils.validators import normalize_phone_number


class MockWhatsAppProvider(WhatsAppProvider):
    """Mock WhatsApp provider for automated tests and offline simulation."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []

    def send_text_message(self, to_phone: str, message: str) -> Dict[str, Any]:
        msg_id = f"mock_msg_{len(self.sent_messages) + 1}"
        record = {
            "to_phone": normalize_phone_number(to_phone),
            "message": message,
            "message_id": msg_id,
            "timestamp": "2026-11-06T00:00:00Z"
        }
        self.sent_messages.append(record)
        return {"success": True, "message_id": msg_id, "error": None}

    def parse_incoming_webhook(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return {
            "from_phone": normalize_phone_number(raw_data.get("from_phone", "+919876543210")),
            "text": raw_data.get("text", "").strip(),
            "message_id": raw_data.get("message_id", "mock_incoming_1"),
            "profile_name": raw_data.get("profile_name", "Mock Patient"),
            "timestamp": "1700000000"
        }

    def clear(self):
        self.sent_messages.clear()
