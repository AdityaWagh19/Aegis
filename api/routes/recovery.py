# api/routes/recovery.py
import csv
import io
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header
from sqlalchemy import select

from models.mandate_event import MandateEvent
from models.db import AsyncSessionLocal, RecoveryDecisionORM, MandateEventORM
from models.tenant import TenantSchema
from api.middleware.auth import get_tenant_from_request
from core.orchestrator import process_batch

router = APIRouter()
logger = logging.getLogger(__name__)

# Security constants
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB upload ceiling (DoS protection)
MAX_BATCH_ROWS = 10_000             # Maximum rows processed per upload

# In-memory batch result cache (keyed by (tenant_id, batch_id))
_batch_cache: dict[tuple[str, str], dict] = {}


@router.post("/recovery/batch", status_code=202)
async def upload_batch(
    file: UploadFile = File(...),
    tenant: TenantSchema = Depends(get_tenant_from_request),
):
    """
    Accept a CSV upload of failed mandate events.
    Enforces maximum file size (10MB) and maximum rows (10,000).
    Scoped to the authenticated tenant.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    # Streaming bounded read to prevent memory exhaustion
    contents = bytearray()
    chunk_size = 1024 * 1024  # 1MB chunks
    while chunk := await file.read(chunk_size):
        contents.extend(chunk)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Payload exceeds maximum allowed size of {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
            )

    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded file must be valid UTF-8 text.")

    reader = csv.DictReader(io.StringIO(text))

    events: list[MandateEvent] = []
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        if len(events) >= MAX_BATCH_ROWS:
            raise HTTPException(
                status_code=400,
                detail=f"Batch exceeds maximum allowed size of {MAX_BATCH_ROWS} rows."
            )
        try:
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
            row["is_revocable"] = row.get("is_revocable", "true").lower() == "true"
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

    logger.info("Processing batch of %d mandate events for tenant=%s", len(events), tenant.tenant_id)
    result = await process_batch(events, tenant_id=tenant.tenant_id)

    # Cache result scoped by tenant_id
    _batch_cache[(tenant.tenant_id, result.batch_id)] = result.model_dump()

    return {
        "batch_id": result.batch_id,
        "status": "complete",
        "record_count": len(events),
        "parse_errors": errors,
        "metrics": result.metrics.model_dump(),
    }


@router.get("/recovery/batch/{batch_id}")
async def get_batch(
    batch_id: str,
    tenant: TenantSchema = Depends(get_tenant_from_request),
):
    """
    Poll batch processing results scoped to the calling tenant.
    """
    cache_key = (tenant.tenant_id, batch_id)
    if cache_key not in _batch_cache:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found for tenant.")
    return _batch_cache[cache_key]


@router.post("/recovery/reset")
async def reset_demo_data(
    tenant: TenantSchema = Depends(get_tenant_from_request),
    admin_key: str | None = Header(default=None, alias="X-Aegis-Admin-Key"),
):
    """
    Reset transaction data (decisions, events, audit log, batch jobs) for a clean demo run.
    Security: Disabled in production unless explicitly authorized via X-Aegis-Admin-Key.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        expected_key = os.getenv("AEGIS_ADMIN_SECRET")
        if not expected_key or admin_key != expected_key:
            raise HTTPException(
                status_code=403,
                detail="Reset endpoint is disabled in production. Valid X-Aegis-Admin-Key required.",
            )

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
    logger.info("Demo database reset executed by tenant=%s", tenant.tenant_id)
    return {"status": "success", "message": "Demo data reset cleanly. Ready for new batch upload."}


