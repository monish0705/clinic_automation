from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class MetaMessage(BaseModel):
    from_: str = ""
    id: str = ""
    timestamp: str = ""
    text: Optional[Dict[str, str]] = None
    type: str = "text"


class MetaValue(BaseModel):
    messaging_product: str = "whatsapp"
    metadata: Dict[str, Any] = {}
    contacts: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    statuses: Optional[List[Dict[str, Any]]] = None


class MetaChange(BaseModel):
    value: MetaValue
    field: str


class MetaEntry(BaseModel):
    id: str
    changes: List[MetaChange]


class MetaWebhookPayload(BaseModel):
    object: str
    entry: List[MetaEntry]


class TwilioWebhookPayload(BaseModel):
    From: str
    Body: str
    ProfileName: Optional[str] = None
    MessageSid: Optional[str] = None
    AccountSid: Optional[str] = None
