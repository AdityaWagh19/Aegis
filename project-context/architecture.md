# Architecture — Aegis

> **Status:** Canonical reference | Update whenever DB schema, components, or data flow changes.

---

## System Overview

Aegis is a two-tier mandate failure diagnosis and recovery pipeline with a deterministic compliance gate as the final authority before any action executes.

### Component Responsibilities

| Component | Responsibility | LLM Used? |
|---|---|---|
| Event Ingester | CSV/JSON parsing, schema validation | No |
| Tier-1 Rule Engine | Decline code lookup, deterministic action | No |
| Tier-2 Groq Agent | Ambiguous case reasoning, Hinglish drafting | Yes (Groq — llama-3.3-70b-versatile) |
| Compliance Gate | Unconditional rule enforcement | No |
| Action Executor | Razorpay API calls + mock stubs | No |
| Audit Log | Append-only decision record | No |
| Dashboard | Recovery metrics visualization | No |

---

## Two-Tier Processing Pipeline

```
[EXTERNAL INPUT]
  CSV or JSON batch of failed/at-risk mandate events
  (~14% realistic bounce-rate distribution)
         |
         | POST /api/v1/recovery/batch
         v
[EVENT INGESTER]
  CSV parsing, Pydantic schema validation
  Batch ID assigned
         |
[TIER 1: Deterministic Rule Engine]
  decline_code lookup table (the 6 categories)
  Resolves ~65-75% of the batch in milliseconds
  Latency target: < 5ms per record
         |
  Only ambiguous/composite/unknown codes fall through
         |
[TIER 2: Groq Reasoning Agent (structured output ONLY)]
  in:  {mandate_id, decline_code, customer_features, history, allowed_actions}
  out: {action: <fixed allow-list>, message_hinglish: str,
        rationale: str, confidence: float, alternatives_considered: list}
  Pydantic validation rejects any action outside ALLOWED_ACTIONS
  Latency target: < 1,000ms per case (P95)
  Must not exceed 35% of total batch
         |
[COMPLIANCE GATE (deterministic, non-LLM, cannot be bypassed)]
  Enforces: max_retry_attempts, 24h pre-debit notice,
            AFA-threshold routing, non-revocable -> escalation-only
  Any violation: REJECTED here, logged as "blocked"
  Latency target: < 5ms per record
         |
[ACTION EXECUTOR]
  RETRY_AFTER_BACKOFF        -> Razorpay Subscriptions API (resume)
  SCHEDULE_POST_SALARY       -> Razorpay Subscriptions API (pause + schedule)
  SEND_UPI_INTENT_PUSH       -> Razorpay Payment Links API (UPI-intent link)
  SEND_MANDATE_RENEWAL_LINK  -> Razorpay Payment Links API (new mandate)
  SEND_HINGLISH_NUDGE        -> Mock notification stub (logs, does not send)
  ESCALATE_TO_HUMAN          -> human_review_queue table, no API call
  NO_ACTION_MONITORING       -> Audit log only
         |
[APPEND-ONLY AUDIT LOG]
  {mandate_id, timestamp, tier_that_decided, proposed_action,
   compliance_check_result, final_action, outcome, rationale,
   confidence, hinglish_message_preview, alternatives_considered}
         |
[DASHBOARD]
  Rs. recovered / Rs. at risk, recovery rate by category,
  Tier-1 vs Tier-2 split, compliance violations caught vs executed,
  human review queue, mandate detail drawer
```

---

## Backend Project Structure

```
Aegis/
|-- api/
|   |-- main.py
|   |-- routes/
|   |   |-- recovery.py       # POST /v1/recovery/batch, GET /v1/recovery/batch/{id}
|   |   |-- mandates.py       # GET /v1/mandates/{id}
|   |   |-- metrics.py        # GET /v1/metrics
|   |   |-- audit.py          # GET /v1/audit
|   |   |-- human_review.py   # GET /v1/human-review
|   |   `-- webhooks.py       # POST /webhooks/razorpay
|-- core/
|   |-- tier1_engine.py       # Deterministic rule lookup — no LLM imports
|   |-- tier2_agent.py        # Groq (Llama) structured output
|   |-- compliance_gate.py    # Unconditional compliance enforcement
|   `-- action_executor.py    # Razorpay + mock stub dispatch
|-- services/
|   |-- razorpay_client.py
|   `-- mock_notification.py
|-- audit/
|   `-- log.py                # Append-only audit write
|-- models/
|   |-- mandate_event.py      # Pydantic model (input schema)
|   |-- recovery_decision.py  # Pydantic model (output schema)
|   `-- db.py                 # SQLAlchemy ORM models
|-- config/
|   `-- loader.py             # compliance_config.yaml loader
|-- synthetic/
|   |-- generator.py          # Mandate event generator
|   |-- held_out.py           # Held-out set management
|   `-- evaluator.py          # Held-out evaluation metrics
|-- tests/
|   |-- unit/
|   |   |-- test_tier1.py
|   |   |-- test_compliance_gate.py
|   |   `-- test_audit.py
|   `-- integration/
|       `-- test_batch_pipeline.py
|-- project-context/          # All documentation
|-- compliance_config.yaml
|-- .env.example
|-- docker-compose.yml
|-- requirements.txt
`-- README.md
```

---

## Frontend Structure

```
dashboard/
`-- src/
    |-- components/
    |   |-- MetricCards.tsx              # Rs. recovered, recovery %, violations
    |   |-- TierSplitChart.tsx           # Tier-1 vs Tier-2 donut chart
    |   |-- RecoveryByCategoryTable.tsx  # Per-category recovery rate table
    |   |-- MandateList.tsx              # Scrollable mandate table
    |   |-- MandateDetailDrawer.tsx      # Full decision trail
    |   |-- ComplianceOverrideCard.tsx   # The key demo component
    |   |-- HinglishMessagePreview.tsx   # Hinglish message preview card
    |   |-- HumanReviewQueue.tsx         # Escalated mandates queue
    |   `-- BatchUploader.tsx            # CSV drag-and-drop
    |-- pages/
    |   |-- Dashboard.tsx
    |   |-- Batch.tsx
    |   `-- Audit.tsx
    |-- api/
    |   `-- aegis.ts                     # API client
    `-- App.tsx
```

---

## Information Architecture (API Routes)

```
Aegis System
|-- /api
|   |-- /v1/recovery/batch              POST — upload and process a batch
|   |-- /v1/recovery/batch/{batch_id}   GET  — get batch results
|   |-- /v1/mandates/{id}              GET  — full decision trail for a mandate
|   |-- /v1/metrics                    GET  — summary metrics
|   |-- /v1/audit                      GET  — paginated audit log
|   |-- /v1/human-review               GET  — human review queue
|   `-- /webhooks/razorpay             POST — receive Razorpay webhook events
|-- /dashboard
|   |-- /                              Summary dashboard
|   |-- /batch                         Batch upload and results
|   |-- /mandates                      Mandate list with detail drawer
|   `-- /audit                         Audit log viewer
|-- /config
|   `-- compliance_config.yaml
`-- /data
    `-- synthetic/                      Generator + held-out set
```

---

## Database Schema

### `mandate_events`

```sql
CREATE TABLE mandate_events (
  mandate_id                UUID PRIMARY KEY,
  customer_id               VARCHAR(100) NOT NULL,
  amount                    INT NOT NULL,             -- INR, integer
  mandate_type              VARCHAR(20) NOT NULL,     -- UPI_AUTOPAY | ENACH
  product_category          VARCHAR(20),              -- subscription | loan_emi | sip | insurance
  decline_code              VARCHAR(50) NOT NULL,
  days_since_salary_credit  INT NOT NULL,
  prior_bounce_count        INT NOT NULL DEFAULT 0,
  is_revocable              BOOLEAN NOT NULL DEFAULT TRUE,
  attempt_number            INT NOT NULL DEFAULT 1,
  event_timestamp           TIMESTAMPTZ NOT NULL,
  batch_id                  UUID NOT NULL,
  is_held_out               BOOLEAN NOT NULL DEFAULT FALSE,
  correct_action            VARCHAR(50)               -- Ground-truth label (evaluation only)
);
```

### `recovery_decisions`

```sql
CREATE TABLE recovery_decisions (
  decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id          UUID NOT NULL REFERENCES mandate_events(mandate_id),
  tier_that_decided   SMALLINT NOT NULL,            -- 1 or 2
  proposed_action     VARCHAR(50) NOT NULL,
  compliance_approved BOOLEAN NOT NULL,
  violation_blocked   BOOLEAN NOT NULL DEFAULT FALSE,
  violation_rule      VARCHAR(100),
  final_action        VARCHAR(50) NOT NULL,
  outcome             VARCHAR(20) NOT NULL,         -- executed | mocked | escalated | failed
  rationale           TEXT,
  confidence          DECIMAL(3,2),
  hinglish_message    TEXT,
  alternatives        JSONB,
  razorpay_response   JSONB,
  decided_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `audit_log` (append-only)

```sql
CREATE TABLE audit_log (
  entry_id    BIGSERIAL PRIMARY KEY,
  mandate_id  UUID NOT NULL,
  decision_id UUID NOT NULL,
  timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload     JSONB NOT NULL
);
-- Append-only enforcement at the database role level:
REVOKE UPDATE, DELETE ON audit_log FROM aegis_app;
```

### `human_review_queue`

```sql
CREATE TABLE human_review_queue (
  review_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id      UUID NOT NULL REFERENCES mandate_events(mandate_id),
  reason          VARCHAR(200) NOT NULL,
  compliance_rule VARCHAR(100),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at     TIMESTAMPTZ,
  resolved_by     VARCHAR(100)
);
```

---

## State Machines

### Batch Lifecycle

```
[UPLOADED]       -> CSV received and parsed
      |
[TIER1_RUNNING]  -> All records processed by rule engine simultaneously
      |
[TIER2_RUNNING]  -> Ambiguous cases queued and processed by Groq (Llama)
      |
[GATE_CHECKING]  -> All proposed actions pass through compliance gate
      |
[EXECUTING]      -> Approved actions execute against Razorpay / mock
      |
[COMPLETE]       -> All records have a final_action and outcome
```

### Per-Mandate State Machine

```
[RECEIVED]
      |
 Tier-1 rule engine
      |
[TIER1_RESOLVED] -> compliance gate -> [EXECUTED | ESCALATED | MOCKED]
      |
 (if is_ambiguous == True)
      |
[TIER2_PENDING]
      |
 Groq LLM call
      |
[TIER2_RESOLVED] -> compliance gate -> [EXECUTED | COMPLIANCE_BLOCKED | ESCALATED | MOCKED]
```

---

## Batch Processing Orchestrator

```python
async def process_batch(events: list[MandateEvent]) -> BatchResult:
    results = []
    for event in events:
        # Tier 1: deterministic
        tier1_result = tier1_engine.classify(event)

        if tier1_result.is_ambiguous:
            # Tier 2: LLM reasoning
            tier2_result = await tier2_agent.reason(event)
            proposed_action = tier2_result.action
            tier_decided = 2
        else:
            proposed_action = tier1_result.action
            tier_decided = 1

        # Compliance Gate: unconditional, always runs
        compliance_result = compliance_gate.check(event, proposed_action)
        final_action = compliance_result.final_action

        # Execute
        hinglish_msg = tier2_result.message_hinglish if tier_decided == 2 else None
        outcome = await action_executor.execute(event, final_action, hinglish_msg)

        # Audit: every decision produces exactly one entry
        audit_log.append(event, proposed_action, compliance_result, final_action, outcome, tier_decided)

        results.append(RecoveryDecision(
            mandate_id=event.mandate_id,
            tier_that_decided=tier_decided,
            proposed_action=proposed_action,
            compliance_result=compliance_result,
            final_action=final_action,
            outcome=outcome,
        ))

    return BatchResult(decisions=results, metrics=compute_metrics(results))
```

---

## Pydantic Models

### `MandateEvent` (Input Schema)

```python
class MandateEvent(BaseModel):
    mandate_id: str               # UUID
    customer_id: str
    amount: int                   # INR, integer
    mandate_type: str             # "UPI_AUTOPAY" | "ENACH"
    product_category: str | None  # "subscription" | "loan_emi" | "sip" | "insurance"
    decline_code: str             # One of the six taxonomy codes
    days_since_salary_credit: int # 0-30
    prior_bounce_count: int       # 0-5
    is_revocable: bool            # False for loan mandates
    attempt_number: int           # 1-3
    timestamp: datetime
    correct_action: str | None    # Ground-truth label (evaluation only, not in production)
```

### `Tier2Result` (LLM Output Schema)

```python
class Tier2Result(BaseModel):
    action: Literal[*ALLOWED_ACTIONS]  # Pydantic rejects anything outside this list
    message_hinglish: str
    rationale: str
    confidence: float              # 0.0 to 1.0
    alternatives_considered: list[str] | None
```

### `EvaluationResult` (Held-Out Metrics)

```python
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

---

## Performance Targets

| Operation | Target Latency (P95) |
|---|---|
| Tier-1 classification per record | < 5ms |
| Tier-2 Groq call per case | < 1,000ms |
| Compliance gate check per record | < 5ms |
| Razorpay API call | < 1,000ms |
| Audit log write per record | < 20ms |
| Full batch of 50 records | < 30s |
| Dashboard page load | < 2,000ms |

---

## Scalability Notes (Post-MVP)

- Tier-1 is embarrassingly parallelizable: process records in parallel with no shared state.
- Tier-2 is the bottleneck: LLM calls are sequential per case but parallelizable with async.
- The compliance gate is a pure function: zero shared state, infinitely parallelizable.
- The audit log is append-only: naturally shardable by `batch_id` or `timestamp`.

---

*Source: Master_Aegis.md §10, §12, §13, §17, §19, §20, §21, §26 | Last updated: 2026-08-23*
