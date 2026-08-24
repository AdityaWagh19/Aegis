# Phase 1: Foundation

> **Status:** [ ] Not started
> **Estimated duration:** Days 1–2
> **Depends on:** Nothing — this is the root phase.

---

## Objective

Establish the complete project skeleton, shared data models, database schema, configuration loading, and synthetic data pipeline. The held-out evaluation set must be generated and locked before any rule-writing begins. Every subsequent phase depends on the outputs of this phase.

---

## Scope

- Project directory structure with all Python packages and `__init__.py` files
- `requirements.txt`, `.gitignore`, `.env.example`, `docker-compose.yml`
- `compliance_config.yaml` with all threshold values
- Pydantic models: `MandateEvent`, `Tier1Result`, `Tier2Result`, `ComplianceResult`, `RecoveryDecision`, `BatchResult`, `EvaluationResult`
- SQLAlchemy ORM models: `mandate_events`, `recovery_decisions`, `audit_log`, `human_review_queue`
- Database initialisation script (creates all tables)
- `config/loader.py` — loads and validates `compliance_config.yaml`
- `synthetic/generator.py` — generates 500 mandate events with the target distribution and splits/locks the held-out set internally
- `synthetic/evaluator.py` — skeleton with `evaluate_held_out_set()` function signature (full implementation in Phase 8)
- Generated CSV files committed to the repository

---

## Design Decisions and Rationale

**D1 — Pydantic v2 for all models.**
All models use Pydantic v2. `MandateEvent` is the canonical input schema; every downstream component receives a validated `MandateEvent` object, never a raw dict. This prevents type errors from propagating across phase boundaries.

**D2 — `correct_action` field is only populated in the synthetic/held-out set.**
`MandateEvent` carries an optional `correct_action: str | None` field. This field is populated by the synthetic generator (ground-truth label for evaluation). In production intake, this field is always `None`. The evaluator checks `correct_action is not None` before using it — no special-casing in the pipeline.

**D3 — SQLite for development, PostgreSQL for production.**
`DATABASE_URL` is read from the environment. All SQLAlchemy code is database-agnostic. The only divergence is the audit-log append-only constraint: for PostgreSQL, this is enforced with `REVOKE UPDATE, DELETE ON audit_log FROM aegis_app`; for SQLite, this is enforced at the application layer by `audit/log.py` never exposing an update or delete method. The application layer constraint is also present in the PostgreSQL configuration for defence in depth.

**D4 — Held-out set is 20% of 500 records = 100 records.**
100 records gives statistically meaningful per-category evaluation given the distribution (the rarest category, `NON_REVOCABLE_HARD_DECLINE` at 5%, yields ~5 held-out records — marginal but acceptable for a 13-day demo). The seed is fixed (`random.seed(42)`) so the split is deterministic and reproducible.

**D5 — `compliance_config.yaml` is the single source of truth for thresholds.**
No threshold value is hardcoded in Python. All callers (compliance gate, Tier-1 engine, evaluator) load from `ComplianceConfig` returned by `config/loader.py`. This makes auditing thresholds trivial and prevents drift between components.

**D6 — All packages have `__init__.py` files.**
This prevents relative import errors across the project and makes `python -m synthetic.generator` work from the repo root.

---

## Sequential Implementation Tasks

### Task 1.1 — Create directory structure

Create the following directories and `__init__.py` files:

```
Aegis/
├── api/
│   └── routes/
├── core/
├── services/
├── audit/
├── models/
├── config/
├── synthetic/
│   └── data/           (gitignored for large files, but held-out CSV is committed)
├── tests/
│   ├── unit/
│   └── integration/
├── dashboard/          (empty, populated in Phase 7)
├── plans/
└── project-context/
```

Create `__init__.py` in: `api/`, `api/routes/`, `core/`, `services/`, `audit/`, `models/`, `config/`, `synthetic/`, `tests/`, `tests/unit/`, `tests/integration/`.

### Task 1.2 — Create `requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
sqlalchemy==2.0.30
aiosqlite==0.20.0
asyncpg==0.29.0
groq==0.9.0
razorpay==1.4.1
pyyaml==6.0.1
faker==25.2.0
python-multipart==0.0.9
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.6
python-dotenv==1.0.1
```

### Task 1.3 — Create `.gitignore`

```gitignore
.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
node_modules/
dashboard/dist/
dashboard/.next/
*.egg-info/
.venv/
venv/
.DS_Store
*.db
data/synthetic.csv
*.log
notification_log.jsonl
```

Note: `data/synthetic_held_out.csv` is NOT gitignored — it is committed so the held-out set is locked in version control.

### Task 1.4 — Create `.env.example`

```bash
# Groq API
GROQ_API_KEY=
GROQ_MODEL_TIER2=llama-3.3-70b-versatile
GROQ_MODEL_TIER2_FAST=llama-3.1-8b-instant
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768

# Razorpay (Test Mode ONLY — rzp_test_* keys)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

# Database
DB_PASSWORD=
DATABASE_URL=sqlite:///./aegis.db

# Application
SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:3000
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

### Task 1.5 — Create `compliance_config.yaml`

```yaml
# compliance_config.yaml
# Committed to repository. No secrets. Thresholds only.
# All compliance gate checks read from this file via config/loader.py.

afa_threshold_general: 15000
afa_threshold_sip_insurance: 100000

max_retry_attempts:
  UPI_AUTOPAY: 3
  ENACH: 2

pre_debit_notice_window_hours: 24

# Synthetic data generation distribution
synthetic_distribution:
  INSUFFICIENT_FUNDS: 0.40
  BANK_TECHNICAL_DECLINE: 0.20
  MANDATE_PAUSED: 0.15
  AFA_REQUIRED: 0.10
  MANDATE_EXPIRED: 0.10
  NON_REVOCABLE_HARD_DECLINE: 0.05
```

### Task 1.6 — Create `docker-compose.yml`

```yaml
version: '3.8'
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./compliance_config.yaml:/app/compliance_config.yaml
      - ./data:/app/data
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

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

volumes:
  pgdata:
```

### Task 1.7 — Create `config/loader.py`

```python
# config/loader.py
import yaml
from pathlib import Path
from pydantic import BaseModel


class MaxRetryAttempts(BaseModel):
    UPI_AUTOPAY: int
    ENACH: int


class SyntheticDistribution(BaseModel):
    INSUFFICIENT_FUNDS: float
    BANK_TECHNICAL_DECLINE: float
    MANDATE_PAUSED: float
    AFA_REQUIRED: float
    MANDATE_EXPIRED: float
    NON_REVOCABLE_HARD_DECLINE: float


class ComplianceConfig(BaseModel):
    afa_threshold_general: int
    afa_threshold_sip_insurance: int
    max_retry_attempts: MaxRetryAttempts
    pre_debit_notice_window_hours: int
    synthetic_distribution: SyntheticDistribution


_config: ComplianceConfig | None = None


def load_config(path: str = "compliance_config.yaml") -> ComplianceConfig:
    global _config
    if _config is None:
        with open(Path(path)) as f:
            data = yaml.safe_load(f)
        _config = ComplianceConfig(**data)
    return _config


def get_config() -> ComplianceConfig:
    """FastAPI dependency — returns the loaded config."""
    return load_config()
```

### Task 1.8 — Create `models/mandate_event.py`

```python
# models/mandate_event.py
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator
import uuid


MANDATE_TYPES = Literal["UPI_AUTOPAY", "ENACH"]
PRODUCT_CATEGORIES = Literal["subscription", "loan_emi", "sip", "insurance"]
DECLINE_CODES = Literal[
    "INSUFFICIENT_FUNDS",
    "AFA_REQUIRED",
    "MANDATE_PAUSED",
    "BANK_TECHNICAL_DECLINE",
    "NON_REVOCABLE_HARD_DECLINE",
    "MANDATE_EXPIRED",
    "UNKNOWN",
]

ALLOWED_ACTIONS = [
    "RETRY_AFTER_BACKOFF",
    "SCHEDULE_POST_SALARY",
    "SEND_UPI_INTENT_PUSH",
    "SEND_MANDATE_RENEWAL_LINK",
    "SEND_HINGLISH_NUDGE",
    "ESCALATE_TO_HUMAN",
    "NO_ACTION_MONITORING",
]

RETRY_ACTIONS = ["RETRY_AFTER_BACKOFF", "SCHEDULE_POST_SALARY"]


class MandateEvent(BaseModel):
    mandate_id: Optional[str] = None   # Optional[str]: empty string from CSV also triggers UUID generation
    customer_id: str
    amount: int                            # INR, integer paise-free
    mandate_type: MANDATE_TYPES
    product_category: Optional[PRODUCT_CATEGORIES] = None
    decline_code: str                      # str not Literal — allows UNKNOWN and future codes
    days_since_salary_credit: int          # 0–30
    prior_bounce_count: int                # 0–5
    is_revocable: bool = True
    attempt_number: int = 1               # 1-indexed
    timestamp: datetime
    batch_id: Optional[str] = None
    is_held_out: bool = False
    correct_action: Optional[str] = None  # Ground truth — populated in synthetic data only

    def model_post_init(self, __context) -> None:
        if not self.mandate_id:  # Catches both None and empty string "" from CSV rows
            self.mandate_id = str(uuid.uuid4())
```

### Task 1.9 — Create `models/recovery_decision.py`

```python
# models/recovery_decision.py
from typing import Literal, Optional
from pydantic import BaseModel


class ComplianceResult(BaseModel):
    approved: bool
    final_action: str
    violation_blocked: bool
    violation_rule: Optional[str] = None


class Tier1Result(BaseModel):
    action: str
    is_ambiguous: bool
    reason: str
    tier: Literal[1] = 1


class Tier2Result(BaseModel):
    action: Literal[
        "RETRY_AFTER_BACKOFF",
        "SCHEDULE_POST_SALARY",
        "SEND_UPI_INTENT_PUSH",
        "SEND_MANDATE_RENEWAL_LINK",
        "SEND_HINGLISH_NUDGE",
        "ESCALATE_TO_HUMAN",
        "NO_ACTION_MONITORING",
    ]
    message_hinglish: str
    rationale: str
    confidence: float          # 0.0 – 1.0
    alternatives_considered: Optional[list[str]] = None
    tier: Literal[2] = 2


class RecoveryDecision(BaseModel):
    mandate_id: str
    tier_that_decided: int               # 1 or 2
    proposed_action: str
    compliance_result: ComplianceResult
    final_action: str
    outcome: str                         # "executed" | "mocked" | "escalated" | "failed"
    rationale: Optional[str] = None
    confidence: Optional[float] = None
    hinglish_message: Optional[str] = None
    alternatives_considered: Optional[list[str]] = None
    razorpay_response: Optional[dict] = None


class BatchMetrics(BaseModel):
    total_records: int
    tier1_count: int
    tier2_count: int
    tier1_pct: float
    recovery_rate: float
    rs_recovered: int
    rs_at_risk: int
    compliance_violations_caught: int
    compliance_violations_executed: int
    false_escalation_rate: Optional[float] = None


class BatchResult(BaseModel):
    batch_id: str
    status: str
    metrics: BatchMetrics
    decisions: list[RecoveryDecision]


class EvaluationResult(BaseModel):
    total_held_out: int
    correct_actions: int
    accuracy: float
    recovery_rate_by_category: dict[str, float]
    false_escalation_rate: float
    tier1_resolution_rate: float
    tier2_resolution_rate: float
    compliance_violations_caught: int
    compliance_violations_executed: int   # Must be 0
```

### Task 1.10 — Create `models/db.py`

```python
# models/db.py
import os
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, JSON,
    BigInteger, ForeignKey, Numeric, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./aegis.db")


class Base(DeclarativeBase):
    pass


class MandateEventORM(Base):
    __tablename__ = "mandate_events"
    mandate_id = Column(String, primary_key=True)
    customer_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    mandate_type = Column(String(20), nullable=False)
    product_category = Column(String(20))
    decline_code = Column(String(50), nullable=False)
    days_since_salary_credit = Column(Integer, nullable=False)
    prior_bounce_count = Column(Integer, nullable=False, default=0)
    is_revocable = Column(Boolean, nullable=False, default=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    batch_id = Column(String, nullable=False)
    is_held_out = Column(Boolean, nullable=False, default=False)
    correct_action = Column(String(50))

    decisions = relationship("RecoveryDecisionORM", back_populates="mandate")


class RecoveryDecisionORM(Base):
    __tablename__ = "recovery_decisions"
    decision_id = Column(String, primary_key=True)
    mandate_id = Column(String, ForeignKey("mandate_events.mandate_id"), nullable=False)
    tier_that_decided = Column(Integer, nullable=False)
    proposed_action = Column(String(50), nullable=False)
    compliance_approved = Column(Boolean, nullable=False)
    violation_blocked = Column(Boolean, nullable=False, default=False)
    violation_rule = Column(String(100))
    final_action = Column(String(50), nullable=False)
    outcome = Column(String(20), nullable=False)
    rationale = Column(Text)
    confidence = Column(Numeric(3, 2))
    hinglish_message = Column(Text)
    alternatives = Column(JSON)
    razorpay_response = Column(JSON)
    decided_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    mandate = relationship("MandateEventORM", back_populates="decisions")


class AuditLogORM(Base):
    __tablename__ = "audit_log"
    entry_id = Column(BigInteger, primary_key=True, autoincrement=True)
    mandate_id = Column(String, nullable=False)
    decision_id = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payload = Column(JSON, nullable=False)


class HumanReviewQueueORM(Base):
    __tablename__ = "human_review_queue"
    review_id = Column(String, primary_key=True)
    mandate_id = Column(String, ForeignKey("mandate_events.mandate_id"), nullable=False)
    reason = Column(String(200), nullable=False)
    compliance_rule = Column(String(100))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(String(100))


engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### Task 1.11 — Create `synthetic/generator.py`

```python
# synthetic/generator.py
"""
Generates synthetic UPI Autopay / e-NACH mandate failure events.
Run before writing ANY Tier-1 rules or compliance logic.
Usage: python -m synthetic.generator --count 500 --output data/synthetic.csv --held-out-pct 0.2
"""
import argparse
import csv
import json
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker

fake = Faker("en_IN")


# Ground-truth action lookup (defines what the CORRECT action is for evaluation)
GROUND_TRUTH = {
    "INSUFFICIENT_FUNDS":         "SCHEDULE_POST_SALARY",
    "AFA_REQUIRED":               "SEND_UPI_INTENT_PUSH",
    "MANDATE_PAUSED":             "SEND_HINGLISH_NUDGE",
    "BANK_TECHNICAL_DECLINE":     "RETRY_AFTER_BACKOFF",
    "NON_REVOCABLE_HARD_DECLINE": "ESCALATE_TO_HUMAN",
    "MANDATE_EXPIRED":            "SEND_MANDATE_RENEWAL_LINK",
}

# Distribution mirrors compliance_config.yaml synthetic_distribution
DISTRIBUTION = {
    "INSUFFICIENT_FUNDS": 0.40,
    "BANK_TECHNICAL_DECLINE": 0.20,
    "MANDATE_PAUSED": 0.15,
    "AFA_REQUIRED": 0.10,
    "MANDATE_EXPIRED": 0.10,
    "NON_REVOCABLE_HARD_DECLINE": 0.05,
}


def generate_event(batch_id: str) -> dict:
    decline_code = random.choices(
        list(DISTRIBUTION.keys()),
        weights=list(DISTRIBUTION.values()),
        k=1
    )[0]

    mandate_type = random.choice(["UPI_AUTOPAY", "ENACH"])
    amount = random.randint(500, 150_000)
    is_revocable = True if decline_code != "NON_REVOCABLE_HARD_DECLINE" else False
    product_category = (
        "loan_emi" if not is_revocable
        else random.choice(["subscription", "sip", "insurance", "subscription", "subscription"])
    )
    attempt_number = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1], k=1)[0]
    # Cap attempt_number at the mandate-type maximum
    max_attempts = 3 if mandate_type == "UPI_AUTOPAY" else 2
    attempt_number = min(attempt_number, max_attempts)

    return {
        "mandate_id": str(uuid.uuid4()),
        "customer_id": f"CUST-{random.randint(1000, 9999)}",
        "amount": amount,
        "mandate_type": mandate_type,
        "product_category": product_category,
        "decline_code": decline_code,
        "days_since_salary_credit": random.randint(0, 30),
        "prior_bounce_count": random.randint(0, 4),
        "is_revocable": is_revocable,
        "attempt_number": attempt_number,
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48))).isoformat(),
        "batch_id": batch_id,
        "is_held_out": False,
        "correct_action": GROUND_TRUTH[decline_code],
    }


def generate_batch(count: int, output_path: str, held_out_pct: float = 0.2, seed: int = 42):
    random.seed(seed)
    batch_id = str(uuid.uuid4())
    events = [generate_event(batch_id) for _ in range(count)]

    # Write full dataset
    fieldnames = list(events[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)

    print(f"Generated {count} events -> {output_path}")

    # Split held-out
    n_held_out = int(count * held_out_pct)
    random.shuffle(events)
    held_out = events[:n_held_out]
    for e in held_out:
        e["is_held_out"] = True

    held_out_path = output_path.replace(".csv", "_held_out.csv")
    with open(held_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(held_out)

    print(f"Held-out set: {n_held_out} events -> {held_out_path}")
    print("IMPORTANT: Commit data/synthetic_held_out.csv before writing any rules.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output", default="data/synthetic.csv")
    parser.add_argument("--held-out-pct", type=float, default=0.2)
    args = parser.parse_args()
    generate_batch(args.count, args.output, args.held_out_pct)
```

### Task 1.12 — Create `synthetic/evaluator.py` (skeleton only)

```python
# synthetic/evaluator.py
"""
Held-out evaluation. Full implementation completed in Phase 8.
The function signature and return type are defined here so Phase 2+
can reference the expected metrics structure.
"""
import csv
from models.recovery_decision import EvaluationResult


def load_held_out_events(path: str = "data/synthetic_held_out.csv") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate_held_out_set() -> EvaluationResult:
    """
    Runs the full pipeline on the held-out set and returns evaluation metrics.
    Full implementation in Phase 8 after process_batch() is available.
    """
    raise NotImplementedError("Implemented in Phase 8 after process_batch() is complete.")
```

### Task 1.13 — Run generator and commit held-out set

```bash
mkdir -p data
python -m synthetic.generator --count 500 --output data/synthetic.csv --held-out-pct 0.2
git add data/synthetic_held_out.csv
git commit -m "data: generate and lock held-out evaluation set (100 records, seed=42)"
```

This commit must exist before any rule-writing begins (Phase 2).

---

## Validation Strategy

After completing all tasks in this phase:

1. `python -c "from config.loader import load_config; c = load_config(); print(c)"` — prints `ComplianceConfig` without error.
2. `python -c "from models.mandate_event import MandateEvent; print('OK')"` — no import error.
3. `python -c "from models.db import init_db; import asyncio; asyncio.run(init_db()); print('Tables created')"` — creates `aegis.db` with all 4 tables.
4. `python -m synthetic.generator --count 500 --output data/synthetic.csv` — completes without error.
5. `wc -l data/synthetic_held_out.csv` — outputs `101` (100 data rows + 1 header).
6. Check that `data/synthetic_held_out.csv` is present in `git status` as a tracked file.

---

## Acceptance Criteria

- [ ] All directories and `__init__.py` files exist.
- [ ] `pip install -r requirements.txt` completes without error.
- [ ] `compliance_config.yaml` loads successfully via `config/loader.py` and produces a `ComplianceConfig` instance with all expected fields.
- [ ] All Pydantic models import without error and accept valid test inputs.
- [ ] `asyncio.run(init_db())` creates all 4 ORM tables in `aegis.db`.
- [ ] `data/synthetic_held_out.csv` exists, contains exactly 100 rows, and is committed to `main`.
- [ ] `data/synthetic.csv` contains exactly 500 rows with all required fields populated.
- [ ] Distribution in `data/synthetic.csv` is within ±5% of targets (check with a count per `decline_code`).
- [ ] `.env.example` exists and documents all required variables.
- [ ] `docker-compose.yml` is valid (`docker compose config` exits with code 0).

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| Held-out set generated after rules are written | High if not enforced | Git commit timestamp of `synthetic_held_out.csv` must precede any commit to `core/` |
| SQLite async driver not installed | Medium | `aiosqlite` is in `requirements.txt`; verify `DATABASE_URL` uses `sqlite+aiosqlite://` prefix |
| Pydantic v2 breaking change vs v1 | Low | All models use v2 syntax from the start |
| `data/` directory gitignored | Medium | `.gitignore` explicitly lists `data/synthetic.csv` (large, regenerable) but NOT `data/synthetic_held_out.csv` |

---

## Deliverables

- All project source files as specified in Tasks 1.1–1.12
- `data/synthetic_held_out.csv` committed to `main`
- `data/synthetic.csv` generated locally (not committed)
- Working `init_db()` that creates all tables

---

## Documentation Updates

- Update `project-context/progress.md` — Day 1 and Day 2 entries
- Check off Phase 1 tasks in `project-context/tasks.md`
- Update `plans/overview.md` Phase 1 status: `[x]`
