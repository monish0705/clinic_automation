import time
from typing import Dict, Any, Optional
import httpx
from app.services.whatsapp.base import WhatsAppProvider
from app.core.config import settings
from app.core.logging import logger
from app.utils.validators import normalize_phone_number


class MetaWhatsAppProvider(WhatsAppProvider):
    """Implementation of official Meta WhatsApp Cloud API (Graph API)."""

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        self.phone_number_id = phone_number_id or settings.META_WA_PHONE_NUMBER_ID
        self.access_token = access_token or settings.META_WA_ACCESS_TOKEN
        self.api_url = f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages"

    def send_text_message(self, to_phone: str, message: str) -> Dict[str, Any]:
        clean_phone = normalize_phone_number(to_phone).replace("+", "")
        if not self.access_token or not self.phone_number_id:
            logger.warning("[META_WA] Cloud API credentials not configured. Simulating delivery.")
            return {"success": True, "message_id": f"sim_meta_{int(time.time()*1000)}", "error": None}

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"preview_url": False, "body": message}
        }

        # Handle retries with backoff
        for attempt in range(2):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(self.api_url, headers=headers, json=payload)

                if resp.status_code in (200, 201):
                    data = resp.json()
                    msg_id = data.get("messages", [{}])[0].get("id", "meta_ok")
                    logger.info(f"[META_WA] Message sent to {clean_phone} | ID: {msg_id}")
                    return {"success": True, "message_id": msg_id, "error": None}

                logger.error(f"[META_WA] API error (HTTP {resp.status_code}): {resp.text}")
                if resp.status_code == 429:  # Rate limited
                    time.sleep(1.0)
                    continue
                return {"success": False, "message_id": None, "error": resp.text}

            except Exception as exc:
                logger.error(f"[META_WA] Delivery error on attempt {attempt+1}: {exc}")
                if attempt == 0:
                    time.sleep(1.0)

        return {"success": False, "message_id": None, "error": "Max retries exceeded"}

    def parse_incoming_webhook(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parses Meta Cloud API Webhook payload structure."""
        try:
            entry = raw_data.get("entry", [])[0]
            change = entry.get("changes", [])[0]
            value = change.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None  # Could be a status receipt (delivered, read)

            msg = messages[0]
            from_phone = msg.get("from", "")
            msg_id = msg.get("id", "")
            timestamp = msg.get("timestamp", "")

            # Get display name from contacts if present
            contacts = value.get("contacts", [])
            profile_name = contacts[0].get("profile", {}).get("name") if contacts else None

            # Extract text
            text_body = ""
            if msg.get("type") == "text":
                text_body = msg.get("text", {}).get("body", "")
            elif msg.get("type") == "button":
                text_body = msg.get("button", {}).get("text", "")
            elif msg.get("type") == "interactive":
                interactive = msg.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    text_body = interactive.get("button_reply", {}).get("title", "")
                elif interactive.get("type") == "list_reply":
                    text_body = interactive.get("list_reply", {}).get("title", "")

            return {
                "from_phone": normalize_phone_number(from_phone),
                "text": text_body.strip(),
                "message_id": msg_id,
                "profile_name": profile_name,
                "timestamp": timestamp,
            }
        except (IndexError, KeyError, TypeError) as exc:
            logger.warning(f"[META_WA] Could not parse webhook data: {exc}")
            return None
