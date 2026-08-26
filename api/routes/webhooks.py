# api/routes/webhooks.py
import hashlib
import hmac
import json
import logging
import os
from fastapi import APIRouter, Request, HTTPException

from dotenv import load_dotenv
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

_redis_pool = None


async def get_redis():
    global _redis_pool
    if _redis_pool is None:
        from arq import create_pool
        from workers.arq_settings import redis_settings
        _redis_pool = await create_pool(redis_settings)
    return _redis_pool


@router.post("/webhooks/razorpay", status_code=200)
async def razorpay_webhook(request: Request):
    """
    Receive and validate Razorpay subscription lifecycle webhook events.
    Verifies HMAC-SHA256 signature before processing.
    Phase 9: resolves tenant by webhook secret, enqueues to ARQ for async processing.
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Phase 9: Look up tenant by webhook_secret hash
    tenant_id = await _resolve_tenant_from_signature(body, signature)
    if not tenant_id:
        # Fallback to global webhook secret (single-tenant MVP mode)
        secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        if secret:
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, signature):
                payload = json.loads(body)
                event_type = payload.get("event", "")
                logger.info("Razorpay webhook (MVP mode): event=%s", event_type)
                return _handle_event(payload, event_type, tenant_id="default")

        logger.warning("Razorpay webhook signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    payload = json.loads(body)
    event_type = payload.get("event", "")
    logger.info("Razorpay webhook: event=%s tenant_id=%s", event_type, tenant_id)
    return _handle_event(payload, event_type, tenant_id=tenant_id)


def _handle_event(payload: dict, event_type: str, tenant_id: str = "default"):
    """Route webhook events to processing."""
    if event_type == "payment.failed" and tenant_id != "default":
        # Phase 9: enqueue to ARQ for async processing
        import asyncio
        asyncio.ensure_future(_enqueue_payment_failed(tenant_id, payload))
        return {"status": "queued", "event": event_type, "tenant_id": tenant_id}

    # MVP mode: acknowledge without processing
    handled = {
        "payment.failed": "Mandate failure detected — will appear in next batch run.",
        "subscription.pending": "Subscription moved to pending.",
        "subscription.charged": "Subscription charged successfully.",
        "subscription.activated": "Subscription activated.",
        "payment.captured": "Payment captured successfully.",
    }

    if event_type in handled:
        return {"status": "received", "event": event_type, "note": handled[event_type]}

    return {"status": "ignored", "event": event_type}


async def _enqueue_payment_failed(tenant_id: str, payload: dict):
    """Enqueue a payment.failed event for async processing by the ARQ worker."""
    try:
        redis = await get_redis()
        job = await redis.enqueue_job(
            "process_payment_failed",
            tenant_id,
            payload,
        )
        logger.info("Enqueued job %s for tenant %s", job.job_id, tenant_id)
    except Exception as e:
        logger.error("Failed to enqueue job for tenant %s: %s", tenant_id, e)


async def _resolve_tenant_from_signature(body: bytes, signature: str) -> str | None:
    """
    Find the tenant whose razorpay_webhook_secret produces a matching HMAC.
    Returns tenant_id if found, None otherwise.
    """
    try:
        from sqlalchemy import select
        from models.db import AsyncSessionLocal, TenantORM
        from models.tenant import decrypt

        async with AsyncSessionLocal() as db:
            tenants = (await db.execute(
                select(TenantORM).where(TenantORM.is_active == True)  # noqa: E712
            )).scalars().all()

        for tenant in tenants:
            if not tenant.razorpay_webhook_secret_enc:
                continue
            try:
                secret = decrypt(tenant.razorpay_webhook_secret_enc)
                expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                if hmac.compare_digest(expected, signature):
                    return tenant.tenant_id
            except Exception:
                continue
    except Exception as e:
        logger.debug("Tenant resolution skipped: %s", e)
    return None
