from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class WhatsAppProvider(ABC):
    """Abstract interface defining required messaging provider capabilities."""

    @abstractmethod
    def send_text_message(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Sends an outbound text message to a patient.
        to_phone: Normalized phone number (e.g. '+919876543210' or 'whatsapp:+919876543210')
        Returns dict containing: {'success': bool, 'message_id': str, 'error': Optional[str]}
        """
        pass

    @abstractmethod
    def parse_incoming_webhook(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parses provider-specific incoming webhook payload into a normalized dict:
        {
            'from_phone': str,
            'text': str,
            'message_id': str,
            'profile_name': Optional[str],
            'timestamp': str
        }
        """
        pass
