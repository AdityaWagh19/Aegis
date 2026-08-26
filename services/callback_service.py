# services/callback_service.py
"""
Sends signed decision callbacks to the client's registered webhook URL.
Mirrors the Razorpay webhook pattern: POST with X-Aegis-Signature header.
"""
import hashlib
import hmac
import json
import logging
import asyncio
from datetime import datetime, timezone
import httpx

from models.recovery_decision import RecoveryDecision

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = [2, 8, 32]   # Exponential backoff


class CallbackService:

    def __init__(self, webhook_url: str, secret: str):
        self.webhook_url = webhook_url
        self.secret = secret

    async def send(self, decision: RecoveryDecision) -> bool:
        payload = {
            "event": "aegis.decision.complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": decision.model_dump(),
        }
        body = json.dumps(payload, default=str).encode()
        signature = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Aegis-Signature": signature,
            "X-Aegis-Event": "aegis.decision.complete",
        }

        for attempt, wait in enumerate(BACKOFF_SECONDS, start=1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(self.webhook_url, content=body, headers=headers)
                if resp.status_code < 300:
                    logger.info("Callback delivered: mandate_id=%s status=%d", decision.mandate_id, resp.status_code)
                    return True
                logger.warning("Callback HTTP %d for mandate_id=%s (attempt %d)",
                               resp.status_code, decision.mandate_id, attempt)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning("Callback error attempt %d: %s", attempt, e)

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(wait)

        logger.error("Callback failed after %d attempts for mandate_id=%s", MAX_ATTEMPTS, decision.mandate_id)
        return False
