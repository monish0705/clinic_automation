import json
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, Form, Query, Header, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.whatsapp_service import WhatsAppService
from app.core.security import verify_meta_signature, verify_twilio_signature
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(tags=["WhatsApp Webhooks"])


# ── Meta WhatsApp Cloud API Webhooks ────────────────────────────

@router.get("/api/v1/webhooks/whatsapp", summary="Meta Webhook Verification")
def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """
    Handles Meta WhatsApp Cloud API webhook handshake verification.
    """
    logger.info(f"[WEBHOOK] Verification request received. Mode: {hub_mode}")
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WA_VERIFY_TOKEN:
        logger.info("[WEBHOOK] Meta verification token verified successfully.")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    logger.warning("[WEBHOOK] Meta verification failed: token mismatch.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch.")


@router.post("/api/v1/webhooks/whatsapp", summary="Meta Webhook Inbound Message Event")
async def handle_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
):
    """
    Receives and processes incoming WhatsApp messages from Meta Cloud API.
    Verifies HMAC-SHA256 signature and handles message deduplication.
    """
    raw_body = await request.body()

    # 1. Signature Verification
    if settings.META_WA_APP_SECRET and not verify_meta_signature(raw_body, x_hub_signature_256, settings.META_WA_APP_SECRET):
        logger.error("[WEBHOOK] Invalid Meta HMAC signature.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.error(f"[WEBHOOK] JSON decoding failed: {exc}")
        return PlainTextResponse("INVALID_JSON", status_code=400)

    # 2. Process message through WhatsAppService
    reply = WhatsAppService.handle_incoming_webhook(db=db, raw_payload=payload, provider_type="meta")
    return {"status": "SUCCESS", "replied": reply is not None}


# ── Twilio WhatsApp Webhooks ───────────────────────────────────

@router.post("/api/v1/webhooks/twilio", summary="Twilio Webhook Inbound Message Event")
async def handle_twilio_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    ProfileName: Optional[str] = Form(None),
    MessageSid: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature")
):
    """
    Receives and processes incoming messages forwarded by Twilio WhatsApp sandbox/number.
    """
    form_data = await request.form()
    form_dict = dict(form_data)

    # Verify Twilio signature if auth token is configured
    if settings.TWILIO_AUTH_TOKEN:
        url = str(request.url)
        if not verify_twilio_signature(url, form_dict, x_twilio_signature, settings.TWILIO_AUTH_TOKEN):
            logger.warning("[WEBHOOK] Invalid Twilio signature header.")

    WhatsAppService.handle_incoming_webhook(
        db=db,
        raw_payload=form_dict,
        provider_type="twilio"
    )
    return PlainTextResponse("OK", status_code=200)


# ── Backward Compatibility Webhook ─────────────────────────────

@router.post("/webhook", summary="Legacy Webhook Endpoint (Backward Compatibility)")
async def handle_legacy_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    ProfileName: Optional[str] = Form(None),
    MessageSid: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Preserves exact URL endpoint '/webhook' used by previous prototype."""
    form_data = await request.form()
    WhatsAppService.handle_incoming_webhook(
        db=db,
        raw_payload=dict(form_data),
        provider_type="twilio"
    )
    return PlainTextResponse("OK", status_code=200)
