from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.conversation import ConversationResponse, MessageResponse
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import require_roles

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations & Audit Logs"])


@router.get("", response_model=List[ConversationResponse], summary="List Patient Conversations (Staff Only)")
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieves conversation sessions and ongoing chat states for receptionist review."""
    return db.query(Conversation).order_by(Conversation.last_interaction_at.desc()).offset(skip).limit(limit).all()


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse], summary="Get Conversation Messages")
def get_conversation_messages(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieves message transcript for a specific conversation session."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).limit(limit).all()
