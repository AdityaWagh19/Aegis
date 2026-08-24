# Phase 9: Production Hardening

> **Status:** [ ] Not started
> **Estimated duration:** Days 14–18 (post-MVP layer)
> **Depends on:** All of Phase 1–7 complete and working
> **Integration model:** Model A — Sidecar (Aegis receives Razorpay webhooks, executes actions, calls client callback)

---

## Objective

Transform the single-tenant, inline-processing MVP into a production-grade multi-tenant system. This phase adds six production capabilities in a strict dependency order: tenant DB layer first, then auth (depends on tenants), then async queue (depends on auth), then client callbacks (depends on queue), then observability (independent, can run in parallel with 9.4), then rate limiting (depends on async queue).

None of the Phase 1–7 core pipeline logic changes. All additions are infrastructure layers around the existing `process_batch()` / `process_single()` functions.

---

## Scope

| Sub-phase | Feature | New files |
|---|---|---|
| 9.1 | Multi-tenancy DB layer | `models/tenant.py`, `models/db.py` additions |
| 9.2 | API key auth middleware | `api/middleware/auth.py` |
| 9.3 | Async job queue (ARQ + Redis) | `workers/mandate_worker.py`, `workers/arq_settings.py` |
| 9.4 | Client callback webhooks | `services/callback_service.py` |
| 9.5 | Observability | `observability/metrics.py`, `observability/logging.py` |
| 9.6 | Tier-2 rate limiter | `core/tier2_rate_limiter.py` |
| 9.7 | Updated routes + docker-compose | Modified `api/routes/webhooks.py`, `api/routes/recovery.py`, `docker-compose.yml` |

---

## Updated Architecture

```
NBFC / Fintech Client
    ├── Razorpay Subscriptions (manages mandates)
    │       └── payment.failed webhook → POST /webhooks/razorpay
    │                                         ├── Verify HMAC
    │                                         ├── Lookup tenant by webhook_secret hash
    │                                         ├── Enqueue job (Redis / ARQ)
    │                                         └── 200 OK (< 1s)
    │
    └── Dashboard users
            └── Authorization: Bearer <api_key>
                    └── Tenant middleware validates key, sets request.state.tenant

Aegis Workers (ARQ)
    └── process_payment_failed(ctx, tenant_id, payload)
             ├── Load tenant compliance config from DB
             ├── Initialise per-tenant Razorpay client (keys from encrypted DB field)
             ├── Call process_single(event, tenant_config)
             ├── Write RecoveryDecision + AuditLog to DB
             └── POST client callback → tenant.webhook_url

Observability
    ├── /metrics Prometheus endpoint
    ├── structlog structured JSON logs
    └── Per-tenant counters: actions, violations, tier2_calls, groq_latency
```

---

## Design Decisions and Rationale

**D1 — ARQ over Celery for the async queue.**
ARQ is asyncio-native. Celery runs a synchronous worker pool — every Groq call would need `asyncio.run()` inside a sync worker, which is inefficient. ARQ workers are async functions that can `await tier2_reason()` directly. ARQ uses Redis as both the broker and result backend.

**D2 — Per-tenant encryption with a master key, not Secrets Manager per key.**
Storing one secret per tenant in AWS Secrets Manager costs $0.40/month per secret and requires an API call per request. For a prototype with < 50 tenants, symmetric encryption (Fernet/AES-256) with a single master key is correct: encrypt tenant keys at DB write time, decrypt at worker instantiation time. The master key comes from one environment variable or one Secrets Manager call at startup.

**D3 — Tenant config is cached in the worker process, not fetched per event.**
`TenantConfigCache` loads and caches `TenantComplianceConfig` with a 5-minute TTL. This avoids a DB round-trip per mandate event at scale. The TTL means config changes propagate within 5 minutes without a deployment.

**D4 — Client callback uses HMAC signed payload.**
Aegis signs the outgoing callback payload with `HMAC-SHA256(payload, tenant.callback_secret)` and sends it in `X-Aegis-Signature`. This mirrors the Razorpay pattern exactly, so NBFC engineering teams already know how to verify it.

**D5 — Prometheus metrics are per-tenant via labels.**
Every counter uses `tenant_id` as a label: `aegis_recovery_actions_total{tenant_id="t_abc", action="RETRY_AFTER_BACKOFF"}`. This allows per-tenant dashboards in Grafana from a single Prometheus instance.

**D6 — Tier-2 rate limiting uses a Redis sliding window, not a token bucket.**
A token bucket refills at a fixed rate, which allows bursts. A sliding window counts actual calls in the last 60 seconds, which is more conservative and matches Groq's rate limit semantics. When the budget is exhausted: downgrade to `llama-3.1-8b-instant` (60 req/min free tier). If that budget is also exhausted: return Tier-1 result with `is_ambiguous_downgraded=True` in the rationale.

---

## Sequential Implementation Tasks

---

### Sub-phase 9.1 — Multi-Tenancy DB Layer

#### Task 9.1.1 — Create `models/tenant.py`

```python
# models/tenant.py
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    master_key = os.getenv("AEGIS_MASTER_ENCRYPTION_KEY")
    if not master_key:
        raise RuntimeError("AEGIS_MASTER_ENCRYPTION_KEY not set.")
    return Fernet(master_key.encode())


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def hash_api_key(api_key: str) -> str:
    """SHA-256 hash of the raw API key. The raw key is only shown at creation time."""
    return hashlib.sha256(api_key.encode()).hexdigest()


class TenantComplianceConfigSchema(BaseModel):
    """Per-tenant compliance thresholds. Overrides compliance_config.yaml defaults."""
    afa_threshold_general: int = 15000
    afa_threshold_sip_insurance: int = 100000
    max_retry_upi_autopay: int = 3
    max_retry_enach: int = 2
    pre_debit_notice_window_hours: int = 24
    tier2_budget_per_minute: int = 10       # Max Groq calls per minute for this tenant


class TenantSchema(BaseModel):
    tenant_id: str
    name: str
    webhook_url: Optional[str] = None
    callback_secret: Optional[str] = None
    is_active: bool = True
    compliance_config: TenantComplianceConfigSchema = TenantComplianceConfigSchema()
```

#### Task 9.1.2 — Add tenant tables to `models/db.py`

Add the following ORM models to the existing `models/db.py` file:

```python
# Append to models/db.py

class TenantORM(Base):
    __tablename__ = "tenants"
    tenant_id = Column(String, primary_key=True, default=lambda: f"t_{uuid.uuid4().hex[:12]}")
    name = Column(String(200), nullable=False, unique=True)
    api_key_hash = Column(String(64), nullable=False, unique=True)   # SHA-256 of raw key
    webhook_url = Column(String(500))          # Where Aegis sends decision callbacks
    callback_secret = Column(String(500))      # Encrypted; used to sign outbound callbacks
    razorpay_key_id_enc = Column(String(500))  # Fernet-encrypted Razorpay key_id
    razorpay_key_secret_enc = Column(String(500))  # Fernet-encrypted Razorpay key_secret
    razorpay_webhook_secret_hash = Column(String(64))  # SHA-256 for webhook verification
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class TenantComplianceConfigORM(Base):
    __tablename__ = "tenant_compliance_configs"
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), primary_key=True)
    afa_threshold_general = Column(Integer, nullable=False, default=15000)
    afa_threshold_sip_insurance = Column(Integer, nullable=False, default=100000)
    max_retry_upi_autopay = Column(Integer, nullable=False, default=3)
    max_retry_enach = Column(Integer, nullable=False, default=2)
    pre_debit_notice_window_hours = Column(Integer, nullable=False, default=24)
    tier2_budget_per_minute = Column(Integer, nullable=False, default=10)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class BatchJobORM(Base):
    __tablename__ = "batch_jobs"
    job_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    status = Column(String(20), nullable=False, default="queued")  # queued|processing|complete|failed
    source = Column(String(20), nullable=False, default="csv_upload")  # csv_upload|webhook
    enqueued_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    record_count = Column(Integer)
    result_payload = Column(JSON)    # BatchResult.model_dump() — replaces in-memory cache
    error = Column(Text)
```

Also add `tenant_id` column to existing tables:

```sql
-- Migration: add tenant_id to existing tables
ALTER TABLE mandate_events ADD COLUMN tenant_id VARCHAR NOT NULL DEFAULT 'default';
ALTER TABLE recovery_decisions ADD COLUMN tenant_id VARCHAR NOT NULL DEFAULT 'default';
ALTER TABLE audit_log ADD COLUMN tenant_id VARCHAR NOT NULL DEFAULT 'default';
ALTER TABLE human_review_queue ADD COLUMN tenant_id VARCHAR NOT NULL DEFAULT 'default';
```

For SQLAlchemy ORM: add `tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)` to `MandateEventORM`, `RecoveryDecisionORM`, `AuditLogORM`, `HumanReviewQueueORM`.

#### Task 9.1.3 — Update `config/loader.py` to support per-tenant config

```python
# config/loader.py — add TenantComplianceConfig loader
from models.tenant import TenantComplianceConfigSchema

def compliance_config_for_tenant(tenant_config: TenantComplianceConfigSchema):
    """
    Converts a TenantComplianceConfigSchema (from DB) to a ComplianceConfig
    compatible with the existing compliance gate and Tier-1 engine.
    """
    from config.loader import ComplianceConfig, MaxRetryAttempts, SyntheticDistribution
    return ComplianceConfig(
        afa_threshold_general=tenant_config.afa_threshold_general,
        afa_threshold_sip_insurance=tenant_config.afa_threshold_sip_insurance,
        max_retry_attempts=MaxRetryAttempts(
            UPI_AUTOPAY=tenant_config.max_retry_upi_autopay,
            ENACH=tenant_config.max_retry_enach,
        ),
        pre_debit_notice_window_hours=tenant_config.pre_debit_notice_window_hours,
        synthetic_distribution=load_config().synthetic_distribution,  # unchanged
    )
```

#### Task 9.1.4 — Admin script to provision a new tenant

```python
# scripts/create_tenant.py
"""
Usage: python scripts/create_tenant.py --name "NBFC Name" --webhook-url https://nbfc.com/aegis/callback
Prints the raw API key (shown once only) and the tenant_id.
"""
import asyncio, argparse, secrets, hashlib, uuid
from models.tenant import encrypt, hash_api_key
from models.db import AsyncSessionLocal, TenantORM, TenantComplianceConfigORM
from models.db import init_db


async def create(name: str, webhook_url: str):
    await init_db()
    raw_api_key = f"aegis_{secrets.token_urlsafe(32)}"
    callback_secret = secrets.token_urlsafe(32)
    tenant = TenantORM(
        name=name,
        api_key_hash=hash_api_key(raw_api_key),
        webhook_url=webhook_url,
        callback_secret=encrypt(callback_secret),
    )
    config = TenantComplianceConfigORM(tenant_id=tenant.tenant_id)
    async with AsyncSessionLocal() as db:
        db.add(tenant)
        db.add(config)
        await db.commit()

    print(f"\nTenant created successfully.")
    print(f"  Tenant ID:       {tenant.tenant_id}")
    print(f"  Name:            {name}")
    print(f"  API Key:         {raw_api_key}  (save this — shown once only)")
    print(f"  Callback Secret: {callback_secret}  (save this — shown once only)")
    print(f"\nConfigure the NBFC's Razorpay key by calling:")
    print(f"  python scripts/set_tenant_razorpay.py --tenant-id {tenant.tenant_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--webhook-url", required=True)
    args = parser.parse_args()
    asyncio.run(create(args.name, args.webhook_url))
```

---

### Sub-phase 9.2 — API Key Auth Middleware

#### Task 9.2.1 — Implement `api/middleware/auth.py`

```python
# api/middleware/auth.py
import hashlib
import logging
from fastapi import Request, HTTPException
from sqlalchemy import select
from models.db import AsyncSessionLocal, TenantORM
from models.tenant import TenantSchema, TenantComplianceConfigSchema

logger = logging.getLogger(__name__)

# In-process tenant cache: api_key_hash -> TenantSchema (TTL via simple dict; use Redis in prod scale)
_tenant_cache: dict[str, TenantSchema | None] = {}


async def get_tenant_from_request(request: Request) -> TenantSchema:
    """
    FastAPI dependency. Validates Authorization: Bearer <api_key> header.
    Sets request.state.tenant for downstream use.
    Raises 401 if header missing, 403 if key invalid or tenant inactive.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or malformed.")

    raw_key = auth_header[len("Bearer "):]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    if key_hash in _tenant_cache:
        tenant = _tenant_cache[key_hash]
        if tenant is None:
            raise HTTPException(status_code=403, detail="Invalid API key.")
        return tenant

    async with AsyncSessionLocal() as db:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(TenantORM)
            .where(TenantORM.api_key_hash == key_hash)
            .where(TenantORM.is_active == True)
        )
        result = await db.execute(stmt)
        tenant_orm = result.scalars().first()

    if not tenant_orm:
        _tenant_cache[key_hash] = None
        logger.warning("Invalid API key presented (hash prefix: %s...)", key_hash[:8])
        raise HTTPException(status_code=403, detail="Invalid API key.")

    # Load compliance config
    async with AsyncSessionLocal() as db:
        from models.db import TenantComplianceConfigORM
        cfg_result = await db.execute(
            select(TenantComplianceConfigORM).where(
                TenantComplianceConfigORM.tenant_id == tenant_orm.tenant_id
            )
        )
        cfg_orm = cfg_result.scalars().first()

    compliance_cfg = TenantComplianceConfigSchema(
        afa_threshold_general=cfg_orm.afa_threshold_general if cfg_orm else 15000,
        afa_threshold_sip_insurance=cfg_orm.afa_threshold_sip_insurance if cfg_orm else 100000,
        max_retry_upi_autopay=cfg_orm.max_retry_upi_autopay if cfg_orm else 3,
        max_retry_enach=cfg_orm.max_retry_enach if cfg_orm else 2,
        tier2_budget_per_minute=cfg_orm.tier2_budget_per_minute if cfg_orm else 10,
    )

    tenant = TenantSchema(
        tenant_id=tenant_orm.tenant_id,
        name=tenant_orm.name,
        webhook_url=tenant_orm.webhook_url,
        compliance_config=compliance_cfg,
    )
    _tenant_cache[key_hash] = tenant
    logger.info("Tenant authenticated: %s (%s)", tenant.name, tenant.tenant_id)
    return tenant
```

#### Task 9.2.2 — Apply auth dependency to routes

In every protected route, add the dependency:

```python
from api.middleware.auth import get_tenant_from_request
from fastapi import Depends

@router.post("/recovery/batch")
async def upload_batch(
    file: UploadFile = File(...),
    tenant: TenantSchema = Depends(get_tenant_from_request),
):
    # tenant.tenant_id is now available for all DB writes
    ...
```

**Routes that require auth:** all `/api/v1/*` routes.
**Routes that do NOT require standard auth:** `/webhooks/razorpay` (uses HMAC verification, see 9.3).

---

### Sub-phase 9.3 — Async Job Queue (ARQ + Redis)

#### Task 9.3.1 — Add ARQ and Redis to `requirements.txt`

```
arq==0.25.0
redis==5.0.4
cryptography==42.0.8
prometheus-fastapi-instrumentator==6.1.0
structlog==24.1.0
```

#### Task 9.3.2 — Implement `workers/arq_settings.py`

```python
# workers/arq_settings.py
import os
from arq.connections import RedisSettings

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_settings = RedisSettings.from_dsn(REDIS_URL)
```

#### Task 9.3.3 — Implement `workers/mandate_worker.py`

```python
# workers/mandate_worker.py
"""
ARQ worker — processes mandate failure events from the Redis job queue.
Each job corresponds to one mandate event from a Razorpay webhook.
"""
import logging
from datetime import datetime, timezone
from arq import create_pool
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

    logger.info("Processing job: tenant_id=%s mandate_id=%s", tenant_id, payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id"))

    async with AsyncSessionLocal() as db:
        # Load tenant + compliance config
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
```

#### Task 9.3.4 — Update `api/routes/webhooks.py` to enqueue instead of process inline

```python
# api/routes/webhooks.py (replace inline processing with enqueue)
import hashlib, hmac, json, logging, os
from fastapi import APIRouter, Request, HTTPException
from arq import create_pool
from workers.arq_settings import redis_settings
from sqlalchemy import select
from models.db import AsyncSessionLocal, TenantORM
from models.tenant import hash_api_key

router = APIRouter()
logger = logging.getLogger(__name__)
_redis_pool = None


async def get_redis():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(redis_settings)
    return _redis_pool


@router.post("/webhooks/razorpay", status_code=200)
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Look up tenant by webhook_secret hash
    tenant_id = await _resolve_tenant_from_signature(body, signature)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    payload = json.loads(body)
    event_type = payload.get("event", "")
    logger.info("Razorpay webhook: event=%s tenant_id=%s", event_type, tenant_id)

    if event_type == "payment.failed":
        redis = await get_redis()
        job = await redis.enqueue_job(
            "process_payment_failed",
            tenant_id,
            payload,
        )
        logger.info("Enqueued job %s for tenant %s", job.job_id, tenant_id)
        return {"status": "queued", "job_id": job.job_id, "event": event_type}

    return {"status": "ignored", "event": event_type}


async def _resolve_tenant_from_signature(body: bytes, signature: str) -> str | None:
    """
    Find the tenant whose razorpay_webhook_secret produces a matching HMAC.
    Returns tenant_id if found, None otherwise.
    """
    async with AsyncSessionLocal() as db:
        tenants = (await db.execute(select(TenantORM).where(TenantORM.is_active == True))).scalars().all()

    from models.tenant import decrypt
    for tenant in tenants:
        if not tenant.razorpay_webhook_secret_hash:
            continue
        # We stored the hash of the secret; to verify HMAC we need the actual secret
        # Store the encrypted secret, not just the hash
        # NOTE: razorpay_webhook_secret_enc field is used here (different from hash)
        try:
            secret = decrypt(getattr(tenant, "razorpay_webhook_secret_enc", ""))
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, signature):
                return tenant.tenant_id
        except Exception:
            continue
    return None
```

#### Task 9.3.5 — Update `core/orchestrator.py` to accept injected config

Add `process_single_with_config()` alongside the existing `process_batch()`:

```python
# core/orchestrator.py — add this function
async def process_single_with_config(
    event: MandateEvent,
    compliance_cfg,               # ComplianceConfig (per-tenant)
    razorpay_client,              # RazorpayClient (per-tenant)
    tenant_id: str,
    db: AsyncSession,
) -> RecoveryDecision:
    """
    Per-tenant version of _process_single().
    Uses injected compliance_cfg and razorpay_client instead of module-level singletons.
    """
    gate = ComplianceGate(config=compliance_cfg)
    event.batch_id = event.batch_id or f"webhook_{tenant_id}"

    tier1_result = tier1_classify(event)
    # (same logic as _process_single, but passes gate and razorpay_client through)
    ...
```

---

### Sub-phase 9.4 — Client Callback Webhooks

#### Task 9.4.1 — Implement `services/callback_service.py`

```python
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
```

---

### Sub-phase 9.5 — Observability

#### Task 9.5.1 — Implement `observability/metrics.py`

```python
# observability/metrics.py
"""
Prometheus metrics for Aegis.
All counters use tenant_id as a label for per-tenant dashboards.
"""
from prometheus_client import Counter, Histogram, Gauge

# Recovery actions dispatched (by type and tenant)
recovery_actions_total = Counter(
    "aegis_recovery_actions_total",
    "Number of recovery actions dispatched",
    ["tenant_id", "action", "outcome"],
)

# Compliance violations caught by the gate
compliance_violations_total = Counter(
    "aegis_compliance_violations_total",
    "Number of compliance violations caught by the gate",
    ["tenant_id", "violation_rule"],
)

# Tier-2 Groq calls
tier2_calls_total = Counter(
    "aegis_tier2_calls_total",
    "Number of Tier-2 Groq LLM calls",
    ["tenant_id", "model", "result"],  # result: success|fallback|error
)

# Groq inference latency
groq_latency_seconds = Histogram(
    "aegis_groq_latency_seconds",
    "Groq API call latency in seconds",
    ["tenant_id", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

# Active batch jobs in the queue
active_jobs_gauge = Gauge(
    "aegis_active_jobs",
    "Number of mandate jobs currently in the processing queue",
    ["tenant_id"],
)
```

#### Task 9.5.2 — Wire metrics into `core/tier2_agent.py`

```python
# In tier2_reason() — wrap Groq call with timing and counter

import time
from observability.metrics import tier2_calls_total, groq_latency_seconds

async def tier2_reason(event: MandateEvent, tenant_id: str = "default") -> Tier2Result:
    start = time.perf_counter()
    model = os.getenv("GROQ_MODEL_TIER2", "llama-3.3-70b-versatile")
    try:
        # ... existing Groq call ...
        result = ...  # existing parse logic
        latency = time.perf_counter() - start
        groq_latency_seconds.labels(tenant_id=tenant_id, model=model).observe(latency)
        tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="success").inc()
        return result
    except Exception:
        tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="fallback").inc()
        return _fallback(event, "groq_error")
```

#### Task 9.5.3 — Expose `/metrics` endpoint in `api/main.py`

```python
# api/main.py — add Prometheus endpoint
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
# Accessible at /metrics — scrape with Prometheus
```

#### Task 9.5.4 — Implement `observability/logging.py` with structlog

```python
# observability/logging.py
import logging
import structlog


def configure_logging(level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
```

---

### Sub-phase 9.6 — Tier-2 Rate Limiter

#### Task 9.6.1 — Implement `core/tier2_rate_limiter.py`

```python
# core/tier2_rate_limiter.py
"""
Redis sliding window rate limiter for Tier-2 Groq calls.
Per-tenant budget: N calls per 60 seconds.
On budget exhaustion: downgrade to llama-3.1-8b-instant.
On secondary budget exhaustion: skip Tier-2, return ESCALATE_TO_HUMAN.
"""
import time
import logging
import os
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_redis: Redis | None = None
WINDOW_SECONDS = 60

PRIMARY_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"
FALLBACK_BUDGET_PER_MINUTE = 30   # Groq free tier for 8b model


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis = Redis.from_url(redis_url, decode_responses=True)
    return _redis


async def select_model_for_tenant(tenant_id: str, primary_budget: int) -> str | None:
    """
    Returns:
      - PRIMARY_MODEL if primary budget available
      - FALLBACK_MODEL if primary exhausted but fallback available
      - None if both exhausted (Tier-2 should be skipped)
    """
    redis = await get_redis()
    now = time.time()
    window_start = now - WINDOW_SECONDS

    primary_key = f"tier2:primary:{tenant_id}"
    fallback_key = f"tier2:fallback:{tenant_id}"

    # Remove expired entries from the sorted set
    await redis.zremrangebyscore(primary_key, 0, window_start)
    primary_count = await redis.zcard(primary_key)

    if primary_count < primary_budget:
        # Add current call to the window
        await redis.zadd(primary_key, {str(now): now})
        await redis.expire(primary_key, WINDOW_SECONDS * 2)
        logger.debug("Tier-2 primary model granted: tenant=%s count=%d/%d", tenant_id, primary_count + 1, primary_budget)
        return PRIMARY_MODEL

    # Primary exhausted — check fallback
    await redis.zremrangebyscore(fallback_key, 0, window_start)
    fallback_count = await redis.zcard(fallback_key)

    if fallback_count < FALLBACK_BUDGET_PER_MINUTE:
        await redis.zadd(fallback_key, {str(now): now})
        await redis.expire(fallback_key, WINDOW_SECONDS * 2)
        logger.info("Tier-2 downgraded to fallback model: tenant=%s", tenant_id)
        return FALLBACK_MODEL

    logger.warning("Tier-2 both budgets exhausted: tenant=%s — skipping LLM", tenant_id)
    return None   # Skip Tier-2 entirely
```

#### Task 9.6.2 — Integrate rate limiter into `core/tier2_agent.py`

```python
# In tier2_reason() — check budget before calling Groq

async def tier2_reason(
    event: MandateEvent,
    tenant_id: str = "default",
    tier2_budget: int = 10,
) -> Tier2Result:
    from core.tier2_rate_limiter import select_model_for_tenant
    model = await select_model_for_tenant(tenant_id, tier2_budget)

    if model is None:
        logger.warning("Tier-2 skipped (budget exhausted): mandate_id=%s", event.mandate_id)
        return Tier2Result(
            action="ESCALATE_TO_HUMAN",
            message_hinglish="Hamare system mein abhi busy hai. Agent se baat karein.",
            rationale="tier2_budget_exhausted",
            confidence=0.0,
        )

    # Proceed with Groq call using `model` variable
    ...
```

---

### Sub-phase 9.7 — Updated `docker-compose.yml`

```yaml
# docker-compose.yml (production-hardened)
version: '3.8'
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./compliance_config.yaml:/app/compliance_config.yaml
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2

  worker:
    build: .
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    command: python -m arq workers.mandate_worker.WorkerSettings

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: aegis
      POSTGRES_USER: aegis
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aegis"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5
    restart: unless-stopped

volumes:
  pgdata:
```

---

## New Environment Variables

Add to `.env.example`:

```bash
# Multi-tenancy + encryption
AEGIS_MASTER_ENCRYPTION_KEY=    # Fernet key — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Redis (job queue + rate limiter)
REDIS_URL=redis://localhost:6379

# Observability
PROMETHEUS_ENABLED=true
```

---

## Validation Strategy

1. **Multi-tenancy:** Create two tenants with different AFA thresholds. POST the same mandate event (amount = Rs. 20,000) as each tenant. Verify Tenant A (general threshold Rs. 15,000) produces `SEND_UPI_INTENT_PUSH` and Tenant B (SIP exemption, threshold Rs. 100,000) produces `RETRY_AFTER_BACKOFF`.

2. **Auth:** `curl -X POST /api/v1/recovery/batch` without header → `401`. With invalid key → `403`. With valid key → `202`.

3. **Async queue:** POST a Razorpay `payment.failed` webhook → response in < 1s with `{"status": "queued"}`. Check Redis queue has one job. Start `arq workers.mandate_worker.WorkerSettings`. Verify job is picked up and decision appears in DB.

4. **Client callback:** Register a mock webhook receiver (e.g. `https://webhook.site/...`). Verify `X-Aegis-Signature` is present and verifiable.

5. **Observability:** Start API, run a batch. `curl /metrics` → verify `aegis_recovery_actions_total` and `aegis_compliance_violations_total` appear.

6. **Rate limiter:** Set `tier2_budget_per_minute=2` for a test tenant. Fire 5 Tier-2-routed mandates in < 60 seconds. Verify first 2 use `llama-3.3-70b-versatile`, next batch uses `llama-3.1-8b-instant`, and any beyond the fallback budget returns `ESCALATE_TO_HUMAN` with `rationale="tier2_budget_exhausted"`.

---

## Acceptance Criteria

- [ ] Two tenants with different `afa_threshold_general` produce different actions for the same mandate amount.
- [ ] API returns `401` with no auth header, `403` with invalid key, `202` with valid key.
- [ ] Webhook `POST /webhooks/razorpay` returns in < 1s and enqueues a job in Redis.
- [ ] ARQ worker processes the job and writes a `RecoveryDecision` to the DB.
- [ ] Client callback is received at registered `webhook_url` with valid `X-Aegis-Signature`.
- [ ] `/metrics` endpoint returns Prometheus text format with at least `aegis_recovery_actions_total` populated.
- [ ] Groq latency histograms appear in `/metrics` after a Tier-2 call.
- [ ] Rate limiter downgrade is observable in logs (`Tier-2 downgraded to fallback model`).
- [ ] Rate limiter exhaustion returns `ESCALATE_TO_HUMAN` with `rationale="tier2_budget_exhausted"`.
- [ ] `docker-compose up` starts `api`, `worker`, `db`, and `redis` — all healthy.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| Fernet key rotation breaks existing encrypted records | Medium | Never rotate without re-encrypting all records; store key version in encrypted field |
| Tenant cache stale after config update | Medium | Clear `_tenant_cache` on config update; 5-min TTL is acceptable |
| Redis unavailable — webhooks not enqueued | Medium | Add a DB fallback queue (write `batch_jobs` row with `status=queued`) |
| ARQ job silently fails | Low | ARQ stores job result/error in Redis; add a failed-job monitor |
| `/metrics` endpoint exposed publicly | Medium | Add Nginx location block to restrict `/metrics` to internal network only |

---

## Deliverables

- `models/tenant.py`
- `models/db.py` (updated with 3 new tables + tenant_id columns)
- `api/middleware/auth.py`
- `workers/mandate_worker.py`
- `workers/arq_settings.py`
- `services/callback_service.py`
- `services/razorpay_client.py` (updated to accept per-tenant credentials)
- `core/tier2_rate_limiter.py`
- `core/orchestrator.py` (updated with `process_single_with_config()`)
- `observability/metrics.py`
- `observability/logging.py`
- `docker-compose.yml` (updated with Redis + worker service)
- `scripts/create_tenant.py`
- `scripts/set_tenant_razorpay.py`
- Updated `.env.example`

---

## Documentation Updates

- Update `project-context/architecture.md` — production architecture section
- Update `project-context/dev-guide.md` — add Redis, ARQ, Fernet, Prometheus to stack table
- Update `plans/overview.md` — add Phase 9 to phase map and dependency graph
- Update `plans/overview.md` Phase 9 status: `[x]` when complete
