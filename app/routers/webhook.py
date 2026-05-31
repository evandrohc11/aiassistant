"""
Twilio WhatsApp inbound webhook.
Stub — full logic wired in Phase 3 & 4.
"""
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
) -> Response:
    """Receive an inbound WhatsApp message from Twilio."""
    # TODO (Phase 4): route Body through the agent pipeline
    twiml = MessagingResponse()
    twiml.message("👋 Assistant is online. Full logic coming in Phase 4.")
    return Response(content=str(twiml), media_type="application/xml")
