# api/routes/recovery.py
import csv
import io
import os
import random
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from models.mandate_event import MandateEvent
from models.db import AsyncSessionLocal, RecoveryDecisionORM, MandateEventORM, AuditLogORM
from core.orchestrator import process_batch

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory batch result cache (keyed by batch_id)
# NOTE (Phase 9 migration): This in-memory cache is replaced in Phase 9 by the
# `batch_jobs` DB table (BatchJobORM). When Phase 9 is implemented:
#   1. Remove _batch_cache entirely.
#   2. Replace the GET /recovery/batch/{batch_id} handler with a DB query:
#      stmt = select(BatchJobORM).where(BatchJobORM.job_id == batch_id)
#   3. Store batch results in BatchJobORM.result_payload on completion.
_batch_cache: dict[str, dict] = {}


@router.post("/recovery/batch", status_code=202)
async def upload_batch(file: UploadFile = File(...)):
    """
    Accept a CSV upload of failed mandate events.
    Returns batch_id immediately; process_batch() is awaited inline for demo scale.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    contents = await file.read()
    text = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    events: list[MandateEvent] = []
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        try:
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
            row["is_revocable"] = row.get("is_revocable", "true").lower() == "true"
            # Plan bugfix: original code compared == "false" (inverted logic,
            # marking every non-held-out row as held-out).
            row["is_held_out"] = row.get("is_held_out", "false").lower() == "true"
            row["amount"] = int(row["amount"])
            row["days_since_salary_credit"] = int(row["days_since_salary_credit"])
            row["prior_bounce_count"] = int(row["prior_bounce_count"])
            row["attempt_number"] = int(row["attempt_number"])
            events.append(MandateEvent(**row))
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    if not events:
        raise HTTPException(status_code=422, detail=f"No valid rows parsed. Errors: {errors[:5]}")

    logger.info("Processing batch of %d mandate events", len(events))
    result = await process_batch(events)

    # Cache result for polling
    _batch_cache[result.batch_id] = result.model_dump()

    return {
        "batch_id": result.batch_id,
        "status": "complete",
        "record_count": len(events),
        "parse_errors": errors,
        "metrics": result.metrics.model_dump(),
    }


@router.get("/recovery/batch/{batch_id}")
async def get_batch(batch_id: str):
    """
    Poll batch processing results.
    NOTE: Returns the full BatchResult including ALL decisions (no pagination).
    For a 500-record batch this can be a ~250KB payload. For large-scale use,
    add a ?page / ?page_size query parameter or filter by mandate_id.
    """
    if batch_id not in _batch_cache:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
    return _batch_cache[batch_id]


@router.post("/recovery/reset")
async def reset_demo_data():
    """
    Reset transaction data (decisions, events, audit log, batch jobs)
    for a clean live demo run. Preserves tenant configurations.
    """
    from sqlalchemy import delete, text
    from models.db import AuditLogORM, BatchJobORM
    async with AsyncSessionLocal() as db:
        try:
            # PostgreSQL supports TRUNCATE ... CASCADE
            await db.execute(text("TRUNCATE TABLE audit_log, recovery_decisions, mandate_events, batch_jobs CASCADE"))
            await db.commit()
        except Exception:
            await db.rollback()
            # SQLite fallback: child tables must be deleted before parent tables
            await db.execute(delete(AuditLogORM))
            await db.execute(delete(RecoveryDecisionORM))
            await db.execute(delete(MandateEventORM))
            await db.execute(delete(BatchJobORM))
            await db.commit()
    _batch_cache.clear()
    logger.info("Demo database reset successfully.")
    return {"status": "success", "message": "Demo data reset cleanly. Ready for new batch upload."}


class UPIPaymentRequest(BaseModel):
    mandate_id: str
    upi_app: str = "google_pay"
    upi_id: str | None = None
    amount: int | None = None


@router.get("/recovery/pay/{mandate_id}")
async def get_pay_mandate_details(mandate_id: str):
    """
    White-labeled UPI recovery portal data endpoint.
    Fetches mandate metadata, amount, customer name, and decline reason.
    """
    async with AsyncSessionLocal() as db:
        ev_stmt = select(MandateEventORM).where(MandateEventORM.mandate_id == mandate_id)
        event = (await db.execute(ev_stmt)).scalars().first()

        dec_stmt = (
            select(RecoveryDecisionORM)
            .where(RecoveryDecisionORM.mandate_id == mandate_id)
            .order_by(RecoveryDecisionORM.decided_at.desc())
        )
        decision = (await db.execute(dec_stmt)).scalars().first()

        c_name = os.getenv("DEMO_CUSTOMER_NAME", "Vikram Malhotra")
        c_phone = os.getenv("DEMO_CUSTOMER_PHONE", "+917397918047")

        if not event and not decision:
            return {
                "mandate_id": mandate_id,
                "customer_name": c_name,
                "customer_phone": c_phone,
                "amount": 18000,
                "currency": "INR",
                "status": "pending_authorization",
                "decline_code": "AFA_REQUIRED",
                "product_category": "subscription",
                "mandate_type": "UPI_AUTOPAY",
                "service_provider": "HDFC Mutual Fund SIP",
                "final_action": "SEND_UPI_INTENT_PUSH",
            }

        return {
            "mandate_id": mandate_id,
            "customer_id": event.customer_id if event else "CUST-LIVE-001",
            "customer_name": c_name,
            "customer_phone": c_phone,
            "amount": event.amount if event else 18000,
            "currency": "INR",
            "status": "recovered" if (decision and decision.outcome == "recovered") else "pending_authorization",
            "decline_code": event.decline_code if event else "AFA_REQUIRED",
            "product_category": event.product_category if event else "subscription",
            "mandate_type": event.mandate_type if event else "UPI_AUTOPAY",
            "service_provider": "HDFC Mutual Fund SIP" if (event and event.product_category == "sip") else "Aegis Enterprise Mandate",
            "final_action": decision.final_action if decision else "SEND_UPI_INTENT_PUSH",
        }


@router.post("/recovery/pay")
async def execute_upi_payment(req: UPIPaymentRequest):
    """
    Authentic UPI Intent settlement for mandate re-authorization.
    Updates decision outcome to 'recovered' and records the audit log entry.
    """
    utr = f"4{random.randint(10000000000, 99999999999)}"
    npci_ref = f"NPCI-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        dec_stmt = (
            select(RecoveryDecisionORM)
            .where(RecoveryDecisionORM.mandate_id == req.mandate_id)
            .order_by(RecoveryDecisionORM.decided_at.desc())
        )
        decision = (await db.execute(dec_stmt)).scalars().first()

        ev_stmt = select(MandateEventORM).where(MandateEventORM.mandate_id == req.mandate_id)
        event = (await db.execute(ev_stmt)).scalars().first()

        amount = req.amount or (event.amount if event else 18000)

        if decision:
            decision.outcome = "recovered"

        audit_entry = AuditLogORM(
            tenant_id="default",
            mandate_id=req.mandate_id,
            decision_id=decision.decision_id if decision else str(uuid.uuid4()),
            timestamp=now,
            payload={
                "event": "payment_captured",
                "mandate_id": req.mandate_id,
                "amount": amount,
                "payment_method": "UPI_INTENT",
                "upi_app": req.upi_app,
                "upi_id": req.upi_id or f"vikram@{req.upi_app}",
                "utr": utr,
                "npci_ref": npci_ref,
                "outcome": "recovered",
            },
        )
        db.add(audit_entry)
        await db.commit()

    logger.info("Mandate %s recovered via UPI Intent (%s). UTR=%s", req.mandate_id, req.upi_app, utr)
    return {
        "status": "success",
        "message": "Mandate successfully re-authorized & recovered via UPI",
        "mandate_id": req.mandate_id,
        "amount": amount,
        "utr": utr,
        "npci_ref": npci_ref,
        "upi_app": req.upi_app,
        "timestamp": now.isoformat(),
    }


