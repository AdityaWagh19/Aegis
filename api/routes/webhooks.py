# api/routes/webhooks.py
import hashlib
import hmac
import json
import logging
import os
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhooks/razorpay", status_code=200)
async def razorpay_webhook(request: Request):
    """
    Receive and validate Razorpay subscription lifecycle webhook events.
    Verifies HMAC-SHA256 signature before processing.
    """
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # HMAC validation
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        logger.warning("Razorpay webhook signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    payload = json.loads(body)
    event_type = payload.get("event", "")
    logger.info("Razorpay webhook received: event=%s", event_type)

    # Map webhook events to processing actions
    handled = {
        "payment.failed": "Mandate failure detected — will appear in next batch run.",
        "subscription.pending": "Subscription moved to pending.",
        "subscription.charged": "Subscription charged successfully.",
        "subscription.activated": "Subscription activated.",
    }

    if event_type in handled:
        return {"status": "received", "event": event_type, "note": handled[event_type]}

    return {"status": "ignored", "event": event_type}
