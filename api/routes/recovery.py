# api/routes/recovery.py
import csv
import io
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy import select

from models.mandate_event import MandateEvent
from models.db import AsyncSessionLocal, RecoveryDecisionORM, MandateEventORM
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
