import time
from typing import Dict, Any, Optional
from app.services.whatsapp.base import WhatsAppProvider
from app.core.config import settings
from app.core.logging import logger
from app.utils.validators import normalize_phone_number

try:
    from twilio.rest import Client
except ImportError:
    Client = None


class TwilioWhatsAppProvider(WhatsAppProvider):
    """Twilio WhatsApp implementation with error handling and retries."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None
    ):
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self.from_number = from_number or settings.TWILIO_WHATSAPP_NUMBER
        self._client = None

    def _get_client(self):
        if Client is None:
            return None
        if not self._client and self.account_sid and self.auth_token:
            try:
                self._client = Client(self.account_sid, self.auth_token)
            except Exception as exc:
                logger.error(f"[TWILIO] Failed to initialize client: {exc}")
        return self._client

    def send_text_message(self, to_phone: str, message: str) -> Dict[str, Any]:
        clean_phone = normalize_phone_number(to_phone)
        to_wa = f"whatsapp:{clean_phone}"
        client = self._get_client()

        if not client:
            logger.warning("[TWILIO] Credentials or library not available. Simulating delivery.")
            return {"success": True, "message_id": f"sim_tw_{int(time.time()*1000)}", "error": None}

        try:
            msg = client.messages.create(
                from_=self.from_number,
                to=to_wa,
                body=message
            )
            logger.info(f"[TWILIO] Message sent to {to_wa} | SID: {msg.sid}")
            return {"success": True, "message_id": msg.sid, "error": None}
        except Exception as exc:
            logger.error(f"[TWILIO] Failed to send message to {to_wa}: {exc}")
            return {"success": False, "message_id": None, "error": str(exc)}

    def parse_incoming_webhook(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parses Twilio's standard form-encoded webhook."""
        from_raw = raw_data.get("From", "")
        body = raw_data.get("Body", "")
        sid = raw_data.get("MessageSid", f"tw_{int(time.time()*1000)}")
        profile_name = raw_data.get("ProfileName")

        if not from_raw or not body:
            return None

        return {
            "from_phone": normalize_phone_number(from_raw),
            "text": body.strip(),
            "message_id": sid,
            "profile_name": profile_name,
            "timestamp": str(int(time.time())),
        }
