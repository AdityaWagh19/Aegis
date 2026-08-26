# workers/mandate_worker.py
"""
ARQ worker — processes mandate failure events from the Redis job queue.
Each job corresponds to one mandate event from a Razorpay webhook.
"""
import logging
from datetime import datetime, timezone

from workers.arq_settings import redis_settings

logger = logging.getLogger(__name__)


async def process_payment_failed(ctx: dict, tenant_id: str, payload: dict) -> dict:
    """
    ARQ job function. Called by the worker process when a job is dequeued.
    ctx: ARQ context (contains Redis connection).
    tenant_id: The tenant whose webhook fired.
    payload: Raw Razorpay payment.failed webhook payload.
    Returns: decision dict (also stored in DB and sent to client callback).
    """
    from models.db import AsyncSessionLocal, TenantORM, TenantComplianceConfigORM
    from sqlalchemy import select
    from models.mandate_event import MandateEvent
    from core.orchestrator import process_single_with_config
    from config.loader import compliance_config_for_tenant
    from models.tenant import TenantComplianceConfigSchema, decrypt
    from services.razorpay_client import RazorpayClient
    from services.callback_service import CallbackService

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    logger.info("Processing job: tenant_id=%s payment_id=%s", tenant_id, payment_entity.get("id"))

    async with AsyncSessionLocal() as db:
        tenant_row = (await db.execute(
            select(TenantORM).where(TenantORM.tenant_id == tenant_id)
        )).scalars().first()
        cfg_row = (await db.execute(
            select(TenantComplianceConfigORM).where(TenantComplianceConfigORM.tenant_id == tenant_id)
        )).scalars().first()

    if not tenant_row:
        logger.error("Tenant not found: %s", tenant_id)
        return {"error": "tenant_not_found"}

    # Build per-tenant compliance config
    tenant_cfg_schema = TenantComplianceConfigSchema(
        afa_threshold_general=cfg_row.afa_threshold_general if cfg_row else 15000,
        afa_threshold_sip_insurance=cfg_row.afa_threshold_sip_insurance if cfg_row else 100000,
        max_retry_upi_autopay=cfg_row.max_retry_upi_autopay if cfg_row else 3,
        max_retry_enach=cfg_row.max_retry_enach if cfg_row else 2,
        tier2_budget_per_minute=cfg_row.tier2_budget_per_minute if cfg_row else 10,
    )
    compliance_cfg = compliance_config_for_tenant(tenant_cfg_schema)

    # Parse Razorpay webhook payload into MandateEvent
    event = _parse_razorpay_webhook(payload, tenant_id)
    if event is None:
        logger.warning("Could not parse webhook payload into MandateEvent")
        return {"error": "parse_failed"}

    # Build per-tenant Razorpay client
    razorpay_key_id = decrypt(tenant_row.razorpay_key_id_enc)
    razorpay_key_secret = decrypt(tenant_row.razorpay_key_secret_enc)
    tenant_razorpay = RazorpayClient(key_id=razorpay_key_id, key_secret=razorpay_key_secret)

    # Run the full pipeline
    async with AsyncSessionLocal() as db:
        decision = await process_single_with_config(
            event=event,
            compliance_cfg=compliance_cfg,
            razorpay_client=tenant_razorpay,
            tenant_id=tenant_id,
            db=db,
        )

    # Send client callback
    if tenant_row.webhook_url:
        callback = CallbackService(
            webhook_url=tenant_row.webhook_url,
            secret=decrypt(tenant_row.callback_secret),
        )
        await callback.send(decision)

    return decision.model_dump()


def _parse_razorpay_webhook(payload: dict, tenant_id: str):
    """
    Parse a Razorpay payment.failed webhook into a MandateEvent.
    Razorpay does not provide all fields Aegis needs — missing fields use safe defaults.
    The NBFC can enrich events via the batch CSV upload route for more accurate classification.
    """
    from models.mandate_event import MandateEvent

    try:
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        notes = entity.get("notes", {})
        return MandateEvent(
            customer_id=entity.get("contact", "unknown"),
            amount=entity.get("amount", 0) // 100,   # Paise to INR
            mandate_type=notes.get("mandate_type", "UPI_AUTOPAY"),
            product_category=notes.get("product_category", "subscription"),
            decline_code=_map_razorpay_error_code(entity.get("error_code", "")),
            days_since_salary_credit=int(notes.get("days_since_salary_credit", 10)),
            prior_bounce_count=int(notes.get("prior_bounce_count", 0)),
            is_revocable=notes.get("is_revocable", "true").lower() == "true",
            attempt_number=int(notes.get("attempt_number", 1)),
            timestamp=datetime.now(timezone.utc),
            batch_id=f"webhook_{tenant_id}",
        )
    except Exception as e:
        logger.error("Webhook parse error: %s", e)
        return None


def _map_razorpay_error_code(razorpay_code: str) -> str:
    """Map Razorpay error codes to Aegis taxonomy codes."""
    mapping = {
        "BAD_REQUEST_ERROR": "BANK_TECHNICAL_DECLINE",
        "GATEWAY_ERROR": "BANK_TECHNICAL_DECLINE",
        "INSUFFICIENT_FUNDS": "INSUFFICIENT_FUNDS",
        "INVALID_UPI_ID": "MANDATE_EXPIRED",
        "PAYMENT_CANCELLED": "MANDATE_PAUSED",
    }
    return mapping.get(razorpay_code, "BANK_TECHNICAL_DECLINE")


class WorkerSettings:
    """ARQ worker configuration."""
    functions = [process_payment_failed]
    redis_settings = redis_settings
    max_jobs = 10          # Concurrent jobs per worker process
    job_timeout = 120      # Max seconds per job
    keep_result = 3600     # Keep job result in Redis for 1 hour


# Run with: python -m arq workers.mandate_worker.WorkerSettings
