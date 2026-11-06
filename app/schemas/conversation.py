from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import MessageDirection


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    direction: MessageDirection
    content: str
    message_id: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: int
    patient_id: int
    phone: str
    current_state: str
    state_metadata: Dict[str, Any]
    last_interaction_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)
