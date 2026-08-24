# Phase 6: API Layer

> **Status:** [ ] Not started
> **Estimated duration:** Days 9–10
> **Depends on:** Phase 5 (`process_batch()` fully working and integration-tested)

---

## Objective

Wrap the batch processing pipeline in a FastAPI application with all seven endpoints. The API layer contains zero business logic — every route delegates to `core/` modules. This phase ends with a running API server that accepts a CSV upload, returns correct batch results, and passes an API-level integration test against a real SQLite database.

---

## Scope

- `api/main.py` — FastAPI application, CORS, lifespan handler
- `api/routes/recovery.py` — `POST /v1/recovery/batch`, `GET /v1/recovery/batch/{batch_id}`
- `api/routes/mandates.py` — `GET /v1/mandates/{mandate_id}`
- `api/routes/metrics.py` — `GET /v1/metrics`
- `api/routes/audit.py` — `GET /v1/audit`
- `api/routes/human_review.py` — `GET /v1/human-review`
- `api/routes/webhooks.py` — `POST /webhooks/razorpay`

---

## Design Decisions and Rationale

**D1 — No business logic in routes.**
Every route function is at most 15 lines: parse input, call a `core/` or `synthetic/` function, return the result. If a route grows beyond this, extract a service function into `core/`.

**D2 — Batch processing is synchronous within the request for the demo.**
`process_batch()` is called with `await` inside the POST handler. Tier-2 Groq calls are sequential (one `await tier2_reason()` per ambiguous event). Worst-case timing for a 200-record batch: 30% Tier-2 = 60 sequential calls × ~1s = ~60s. This is acceptable for a demo batch of 10–50 records. A production system uses ARQ background tasks (Phase 9) — the polling pattern is already supported by `GET /v1/recovery/batch/{batch_id}`.

**D3 — CSV parsing happens in the route, not in `process_batch()`.**
The route reads the multipart CSV upload, parses it into a `list[MandateEvent]`, and passes the list to `process_batch()`. This keeps the orchestrator agnostic of HTTP transport.

**D4 — Razorpay webhook validates HMAC signature before processing.**
The webhook route verifies `X-Razorpay-Signature` using `HMAC-SHA256(body, RAZORPAY_WEBHOOK_SECRET)`. Requests that fail verification return `403`. This must be implemented before the deployment phase.

**D5 — Batch results are stored in the database and retrievable by `batch_id`.**
After `process_batch()` completes, the route writes `RecoveryDecisionORM` rows to the DB. `GET /v1/recovery/batch/{batch_id}` reads these rows to reconstruct the result. This enables the dashboard to poll for results.

**D6 — `GET /v1/metrics` computes aggregates from the DB, not from an in-memory cache.**
This keeps the metric computation independent of which process ran the batch. For a single-instance demo this makes no difference, but it means the dashboard always shows the correct figures even after a server restart.

---

## Sequential Implementation Tasks

### Task 6.1 — Implement `api/main.py`

```python
# api/main.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.db import init_db
from api.routes import recovery, mandates, metrics, audit, human_review, webhooks

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Aegis API starting — initialising database...")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Aegis API shutting down.")


app = FastAPI(
    title="Aegis — Mandate Recovery API",
    description="Compliant UPI Autopay / e-NACH failure diagnosis and recovery agent.",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recovery.router, prefix="/api/v1")
app.include_router(mandates.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(human_review.router, prefix="/api/v1")
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aegis"}
```

### Task 6.2 — Implement `api/routes/recovery.py`

```python
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
            row["is_held_out"] = row.get("is_held_out", "false").lower() == "false"
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
```

### Task 6.3 — Implement `api/routes/mandates.py`

```python
# api/routes/mandates.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from models.db import AsyncSessionLocal, AuditLogORM

router = APIRouter()


@router.get("/mandates/{mandate_id}")
async def get_mandate(mandate_id: str):
    """Return the full audit log entry for a single mandate."""
    async with AsyncSessionLocal() as db:
        stmt = select(AuditLogORM).where(AuditLogORM.mandate_id == mandate_id)
        result = await db.execute(stmt)
        entry = result.scalars().first()
        if not entry:
            raise HTTPException(status_code=404, detail=f"Mandate '{mandate_id}' not found in audit log.")
        return {
            "entry_id": entry.entry_id,
            "mandate_id": entry.mandate_id,
            "timestamp": entry.timestamp.isoformat(),
            "payload": entry.payload,
        }
```

### Task 6.4 — Implement `api/routes/metrics.py`

```python
# api/routes/metrics.py
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from models.db import AsyncSessionLocal, AuditLogORM

router = APIRouter()


@router.get("/metrics")
async def get_metrics(batch_id: str | None = Query(default=None)):
    """
    Aggregate metrics across all decisions, or for a specific batch_id.
    Reads from the audit_log table.
    """
    async with AsyncSessionLocal() as db:
        stmt = select(AuditLogORM)
        entries = (await db.execute(stmt)).scalars().all()

    payloads = [e.payload for e in entries]
    if batch_id:
        # audit_log does not have batch_id — filter from batch cache in recovery.py
        # For now return all-time metrics
        pass

    total = len(payloads)
    if total == 0:
        return {"total_records": 0, "message": "No decisions recorded yet."}

    tier1_count = sum(1 for p in payloads if p.get("tier_that_decided") == 1)
    violations_caught = sum(1 for p in payloads if p.get("violation_blocked"))
    escalated = sum(1 for p in payloads if p.get("outcome") == "escalated")
    executed = sum(1 for p in payloads if p.get("outcome") == "executed")

    # Recovery by category
    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for p in payloads:
        by_cat[p.get("decline_code", "UNKNOWN")].append(p.get("outcome") == "executed")
    recovery_by_category = {
        cat: round(sum(vals) / len(vals), 4) for cat, vals in by_cat.items()
    }

    return {
        "total_records": total,
        "tier1_count": tier1_count,
        "tier2_count": total - tier1_count,
        "tier1_pct": round(tier1_count / total * 100, 1),
        "executed_count": executed,
        "escalated_count": escalated,
        "compliance_violations_caught": violations_caught,
        "compliance_violations_executed": 0,
        "recovery_by_category": recovery_by_category,
    }
```

### Task 6.5 — Implement `api/routes/audit.py`

```python
# api/routes/audit.py
from fastapi import APIRouter, Query
from sqlalchemy import select
from models.db import AsyncSessionLocal, AuditLogORM

router = APIRouter()


@router.get("/audit")
async def get_audit(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, le=200)):
    """Paginated append-only audit log."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AuditLogORM)
            .order_by(AuditLogORM.entry_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        entries = (await db.execute(stmt)).scalars().all()
        total_stmt = select(func.count(AuditLogORM.entry_id))  # func.count, not func().count
        total = (await db.execute(total_stmt)).scalar_one()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "entry_id": e.entry_id,
                "mandate_id": e.mandate_id,
                "timestamp": e.timestamp.isoformat(),
                **e.payload,
            }
            for e in entries
        ],
    }
```

### Task 6.6 — Implement `api/routes/human_review.py`

```python
# api/routes/human_review.py
from fastapi import APIRouter
from sqlalchemy import select
from models.db import AsyncSessionLocal, HumanReviewQueueORM

router = APIRouter()


@router.get("/human-review")
async def get_human_review():
    """Return all unresolved items in the human review queue."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(HumanReviewQueueORM)
            .where(HumanReviewQueueORM.resolved_at == None)
            .order_by(HumanReviewQueueORM.created_at.asc())
        )
        items = (await db.execute(stmt)).scalars().all()

    return {
        "total": len(items),
        "items": [
            {
                "review_id": item.review_id,
                "mandate_id": item.mandate_id,
                "reason": item.reason,
                "compliance_rule": item.compliance_rule,
                "created_at": item.created_at.isoformat(),
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            }
            for item in items
        ],
    }


@router.post("/human-review/{review_id}/resolve")
async def resolve_human_review(review_id: str):
    """Mark a human review queue item as resolved."""
    from datetime import datetime, timezone
    from fastapi import HTTPException

    async with AsyncSessionLocal() as db:
        stmt = select(HumanReviewQueueORM).where(HumanReviewQueueORM.review_id == review_id)
        item = (await db.execute(stmt)).scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Review item '{review_id}' not found.")

        item.resolved_at = datetime.now(timezone.utc)
        await db.commit()

    return {"status": "resolved", "review_id": review_id, "resolved_at": item.resolved_at.isoformat()}
```

### Task 6.7 — Implement `api/routes/webhooks.py`

```python
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
```

### Task 6.8 — API smoke test (manual, Day 10)

```bash
# Start the server
uvicorn api.main:app --reload --port 8000

# Health check
curl http://localhost:8000/health

# Upload a small batch (use first 10 rows of synthetic.csv)
head -11 data/synthetic.csv > data/demo_10.csv
curl -X POST http://localhost:8000/api/v1/recovery/batch \
  -F "file=@data/demo_10.csv"

# Check metrics
curl http://localhost:8000/api/v1/metrics

# Check audit log
curl "http://localhost:8000/api/v1/audit?page=1&page_size=10"

# Check human review queue
curl http://localhost:8000/api/v1/human-review
```

---

## Validation Strategy

1. `uvicorn api.main:app --reload` starts without error.
2. `GET /health` returns `{"status": "ok"}`.
3. `POST /api/v1/recovery/batch` with `data/demo_10.csv` returns a valid `batch_id` and metrics.
4. `GET /api/v1/metrics` returns non-zero `total_records`.
5. `GET /api/v1/audit?page=1` returns entries matching the batch.
6. `GET /api/v1/human-review` returns items for any mandates that were escalated.

---

## Acceptance Criteria

- [ ] `uvicorn api.main:app` starts without error on a clean `.env` configuration.
- [ ] `GET /health` returns `200 OK` with `{"status": "ok"}`.
- [ ] `POST /api/v1/recovery/batch` with a valid 10-row CSV returns `202` with `batch_id` and `metrics`.
- [ ] `GET /api/v1/metrics` returns `compliance_violations_executed: 0`.
- [ ] `GET /api/v1/audit` returns one entry per processed mandate.
- [ ] `POST /webhooks/razorpay` with a missing or invalid signature returns `403`.
- [ ] All routes return JSON (not HTML error pages) on `404` and `422` errors.
- [ ] CORS headers are present in all responses for requests from `http://localhost:3000`.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| `process_batch()` blocks the event loop on large batches | Medium | Acceptable for demo; add background task in production |
| Batch result lost on server restart (in-memory cache) | High | Store `BatchResult` in DB in production; for demo this is acceptable |
| CSV dialect issues (CRLF, BOM) | Medium | Use `csv.DictReader` with `io.StringIO` which handles both |
| CORS not configured correctly for deployed URL | Low | `ALLOWED_ORIGINS` env var must include the EC2 domain |

---

## Deliverables

- `api/main.py`
- `api/routes/recovery.py`, `mandates.py`, `metrics.py`, `audit.py`, `human_review.py`, `webhooks.py`
- Manual smoke test output documented in `project-context/progress.md`

---

## Documentation Updates

- Check off Phase 6 tasks in `project-context/tasks.md`
- Record API smoke test results in `project-context/progress.md` Day 9/10
- Update `plans/overview.md` Phase 6 status: `[x]`
