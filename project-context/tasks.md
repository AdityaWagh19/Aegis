# Task List — Aegis

> **Status:** Living document. Updated multiple times per day during the build.
> Mark `[/]` when starting a task, `[x]` when complete.
> Never delete completed items — the history is part of the BUILD_LOG.
> **Phase numbering matches `plans/overview.md`.** Read `plans/phase-N-*.md` for the full implementation spec of each phase.

---

## Phase 1 — Foundation (Days 1–2: Aug 23–24)

### Repository Setup

- [x] Git repository initialized
- [x] `.git` visible (hidden attribute removed)
- [x] First commit pushed to `github.com/AdityaWagh19/Aegis`
- [x] `project-context/` directory created with all 11 documents
- [x] `README.md` created and pushed
- [ ] `.gitignore` created (exclude `.env`, `__pycache__`, `node_modules`, `*.pyc`, `data/held_out*`)
- [ ] `.env.example` created and committed
- [ ] `compliance_config.yaml` created and committed

### Backend Skeleton

- [ ] `requirements.txt` (fastapi, uvicorn, groq, razorpay, sqlalchemy, pydantic, pyyaml, faker, pytest, pytest-asyncio, alembic)
- [ ] `api/main.py` — FastAPI app with health check, CORS, lifespan
- [ ] `models/mandate_event.py` — Pydantic `MandateEvent` with all fields including `product_category`
- [ ] `models/recovery_decision.py` — `Tier1Result`, `Tier2Result`, `ComplianceResult`, `RecoveryDecision`, `BatchResult`
- [ ] `models/db.py` — SQLAlchemy ORM table definitions (mandate_events, recovery_decisions, audit_log, human_review_queue)
- [ ] `config/loader.py` — `ComplianceConfig` dataclass, `load_config()` loader
- [ ] Database migrations: `alembic init` + first migration, `init_db.py` script

### Synthetic Data (Must complete BEFORE any rule-writing)

- [ ] `synthetic/generator.py` — 500 mandate events with correct distribution:
  - INSUFFICIENT_FUNDS: 40%; BANK_TECHNICAL_DECLINE: 20%; MANDATE_PAUSED: 15%
  - AFA_REQUIRED: 10%; MANDATE_EXPIRED: 10%; NON_REVOCABLE_HARD_DECLINE: 5%
- [ ] `synthetic/held_out.py` — splits and locks held-out set (20% = 100 records)
- [ ] Generate and commit `data/synthetic_held_out.csv` — **MUST do before Day 3**
- [ ] `synthetic/evaluator.py` — `evaluate_held_out_set()` function
- [ ] Verify distribution within 5% tolerance of targets

### EC2 Setup

- [ ] EC2 instance launched (Ubuntu 22.04, t3.medium), Elastic IP assigned
- [ ] Security groups open: ports 22, 80, 443
- [ ] Docker + Docker Compose + Nginx + certbot installed
- [ ] `/home/ubuntu/Aegis/.env` created with all real values
- [ ] Nginx config created and enabled; SSL via certbot
- [ ] Razorpay test Plan + Subscription created for charge simulator
- [ ] GitHub repo secrets: `EC2_HOST`, `EC2_SSH_PRIVATE_KEY`, `EC2_USERNAME`

### Phase 1 Acceptance Criteria

- [ ] `pytest tests/unit/test_models.py -v` — all pass
- [ ] `python -m synthetic.generator` produces 500-row CSV
- [ ] `data/synthetic_held_out.csv` committed; never modified after this point
- [ ] `GET /health` returns `{ "status": "ok" }`

---

## Phase 2 — Tier-1 Rule Engine (Days 3–4: Aug 25–26)

- [ ] `core/tier1_engine.py` — `classify(event, config) -> Tier1Result`
  - [ ] `INSUFFICIENT_FUNDS` (high-bounce escalation when `prior_bounce_count >= 3`)
  - [ ] `AFA_REQUIRED` (clear: amount > threshold; borderline: within 10% → ambiguous)
  - [ ] `MANDATE_PAUSED` → `SEND_HINGLISH_NUDGE`
  - [ ] `BANK_TECHNICAL_DECLINE` (attempt < max → `RETRY_AFTER_BACKOFF`; at max → ambiguous)
  - [ ] `NON_REVOCABLE_HARD_DECLINE` → `ESCALATE_TO_HUMAN` (never ambiguous)
  - [ ] `MANDATE_EXPIRED` → `SEND_MANDATE_RENEWAL_LINK`
  - [ ] Unknown decline code → `is_ambiguous=True, reason="unknown_decline_code"`
- [ ] Verify: zero LLM imports in `core/tier1_engine.py`
- [ ] `tests/unit/test_tier1.py` — all 10+ test cases from `test.md`
- [ ] `test_tier1_makes_no_llm_calls` — mock patch confirms zero LLM calls

### Phase 2 Acceptance Criteria

- [ ] All `test_tier1.py` tests pass
- [ ] Tier-1 latency P95 < 5ms on 500 records
- [ ] Tier-1 resolves 65–75% of generated dataset

---

## Phase 3 — Compliance Gate (Day 5: Aug 27)

- [ ] `core/compliance_gate.py` — `check(event, proposed_action, config) -> ComplianceResult`
  - [ ] Rule 1: Non-revocable hard decline — any action != `ESCALATE_TO_HUMAN` blocked
  - [ ] Rule 2: Max retry attempts cap
  - [ ] Rule 3: AFA threshold routing → redirect to `SEND_UPI_INTENT_PUSH`
  - [ ] Rule 4: 24h pre-debit notice → redirect to `SEND_HINGLISH_NUDGE`
- [ ] Verify: zero imports from `tier1_engine.py` or `tier2_agent.py`
- [ ] `tests/unit/test_compliance_gate.py` — all test cases from `test.md`
  - [ ] Every rule has activation test + pass-through test

### Phase 3 Acceptance Criteria

- [ ] All `test_compliance_gate.py` tests pass — zero failures
- [ ] Gate is a pure function; no LLM imports

---

## Phase 4 — Tier-2 Groq Agent (Days 6–7: Aug 28–29)

- [ ] `services/groq_client.py` — lazy singleton `AsyncGroq` client
- [ ] `core/tier2_agent.py` — `tier2_reason(event, config) -> Tier2Result`
  - [ ] Groq tool schema: `action` enum, `message_hinglish`, `confidence`, `alternatives_considered`
  - [ ] `SYSTEM_PROMPT` with taxonomy, allow-list, 3 Hinglish examples
  - [ ] Two-step prompt: classify (temperature=0.1), then draft message (temperature=0.2)
  - [ ] `if not choice.message.tool_calls:` guard before indexing (Groq reliability risk)
  - [ ] Pydantic validation of tool call JSON — rejects out-of-allow-list action
  - [ ] Fallback on `ValidationError`, `APIError`, timeout → `ESCALATE_TO_HUMAN`
- [ ] `tests/unit/test_tier2_schema.py` — schema validation, fallback, allow-list enforcement

### Phase 4 Acceptance Criteria

- [ ] All `test_tier2_schema.py` tests pass
- [ ] `test_pydantic_rejects_out_of_allow_list_action` passes
- [ ] `test_tier2_fallback_on_malformed_output` passes

---

## Phase 5 — Action Executor + Audit Log (Days 8–9: Aug 30–31)

- [ ] `services/razorpay_client.py` — `resume_subscription()`, `pause_subscription()`, `create_payment_link()`
- [ ] `services/mock_notification.py` — `MockNotificationService` logging to `notification_log.jsonl`
- [ ] `core/action_executor.py` — routes `compliance_result.final_action` to execution
- [ ] `audit/log.py` — `append_audit_entry()` — append-only write
- [ ] `core/orchestrator.py` — `process_single()`, `process_batch()` → `BatchResult`
- [ ] `tests/unit/test_audit.py` — append-only constraint, one entry per mandate
- [ ] `tests/integration/test_batch_pipeline.py`:
  - [ ] Full pipeline: Tier-1 resolves 65–75%
  - [ ] Deliberate violation: Tier-2 proposes retry on non-revocable → gate catches → `ESCALATE_TO_HUMAN`
  - [ ] Every record produces exactly one audit entry

### Phase 5 Acceptance Criteria

- [ ] `process_batch()` returns `BatchResult`
- [ ] Razorpay test-mode API calls succeed
- [ ] All integration tests pass
- [ ] `compliance_violations_executed == 0` assertion holds on test batch

---

## Phase 6 — API Layer (Days 9–10: Sep 1–2)

- [ ] `api/routes/recovery.py` — `POST /api/v1/recovery/batch` (sync CSV upload, returns `{status:"complete", metrics:{...}}`), `GET /api/v1/recovery/batch/{batch_id}`
- [ ] `api/routes/mandates.py` — `GET /api/v1/mandates/{id}`
- [ ] `api/routes/metrics.py` — `GET /api/v1/metrics`
- [ ] `api/routes/audit.py` — `GET /api/v1/audit` (paginated; use `func.count()` not `func().count()`)
- [ ] `api/routes/human_review.py` — `GET /api/v1/human-review`
- [ ] `api/routes/webhooks.py` — `POST /webhooks/razorpay` (HMAC validate, inline processing; Phase 9 replaces with ARQ enqueue)
- [ ] Note `_batch_cache` in recovery.py as Phase 9 migration target
- [ ] Register all routers in `api/main.py`

### Phase 6 Acceptance Criteria

- [ ] `POST /api/v1/recovery/batch` returns `{status:"complete", metrics:{...}}` for valid CSV
- [ ] All endpoints return shapes matching `project-context/api.md`
- [ ] `POST /webhooks/razorpay` returns 200 (valid HMAC), 403 (invalid HMAC)

---

## Phase 7 — Dashboard (Days 10–11: Sep 2–3)

- [ ] React app initialized in `dashboard/`
- [ ] `dashboard/src/api/aegis.ts` — typed client for all endpoints
- [ ] `components/MetricCards.tsx` — Rs. recovered, recovery %, violations
- [ ] `components/TierSplitChart.tsx` — Tier-1 vs Tier-2 donut (Recharts)
- [ ] `components/RecoveryByCategoryTable.tsx` — per-category recovery rate
- [ ] `components/MandateList.tsx` — scrollable mandate table
- [ ] `components/MandateDetailDrawer.tsx` — full decision trail on click
- [ ] `components/ComplianceOverrideCard.tsx` — THE demo-critical component
- [ ] `components/HinglishMessagePreview.tsx` — message preview card
- [ ] `components/HumanReviewQueue.tsx` — escalated mandates
- [ ] `components/BatchUploader.tsx` — CSV drag-and-drop (react-dropzone)
- [ ] Pages: `Dashboard.tsx`, `Batch.tsx`, `Audit.tsx`
- [ ] Manual end-to-end test: upload demo CSV → all components render

### Phase 7 Acceptance Criteria

- [ ] Dashboard at `http://localhost:3000`, no console errors
- [ ] `ComplianceOverrideCard` shows correct override data for non-revocable case
- [ ] Hinglish message visible for at least one `MANDATE_PAUSED` case

---

## Phase 8 — Evaluation + Submission (Days 12–13: Sep 3–5)

- [ ] `pytest tests/unit/ -v` — all pass, zero failures
- [ ] `pytest tests/unit/test_compliance_gate.py -v` — all pass
- [ ] `pytest tests/integration/ -v` — all pass
- [ ] Run `python -m synthetic.evaluator` on held-out set
  - [ ] Assert `compliance_violations_executed == 0` — hard stop if this fails
  - [ ] Record honest metrics: accuracy, tier split, false escalation rate
  - [ ] If Tier-2 rate > 30%: add Tier-1 rules before proceeding
- [ ] Verify dashboard displays held-out metrics correctly
- [ ] Create demo batch CSV (50+ records; includes MAND-042 non-revocable case)
- [ ] `README.md` final polish; architecture diagram committed
- [ ] `project-context/progress.md` copied to `BUILD_LOG.md` in repo root
- [ ] Demo rehearsed 3+ times per `project-context/demo.md`
- [ ] All items in `demo.md` Pre-Demo Checklist checked
- [ ] 5-minute video recorded — compliance override moment is unmissable
- [ ] All items in `demo.md` Submission Checklist checked
- [ ] Final push to `main`, GitHub Actions deploy passes
- [ ] Submission completed on platform

### Phase 8 Acceptance Criteria

- [ ] `compliance_violations_executed == 0` asserted programmatically
- [ ] Tier-1 resolution rate 60–80% on held-out set
- [ ] Demo video: override moment visible within 3:30
- [ ] `BUILD_LOG.md` in repo root with at least 8 genuine daily entries

---

## Phase 9 — Production Hardening (Days 14–18: post-submission)

> Attempt only after Phase 8 is complete. See `plans/phase-9-production-hardening.md`.

### 9.1 — Multi-Tenancy DB Layer

- [ ] `models/tenant.py` — `TenantORM`, `TenantComplianceConfigORM`, `BatchJobORM`
- [ ] `models/db.py` updated — `tenant_id` column on existing tables
- [ ] `scripts/create_tenant.py` — admin provisioning script
- [ ] `scripts/set_tenant_razorpay.py` — Fernet-encrypted credential setter
- [ ] Alembic migration for all new tables

### 9.2 — API Key Auth Middleware

- [ ] `api/middleware/auth.py` — SHA-256 hash lookup, 5-min in-process cache
- [ ] Registered in `api/main.py` — `/api/v1/` protected; `/webhooks/`, `/health` exempt
- [ ] `tests/unit/test_auth_middleware.py` — 401, 403, 202, inactive tenant cases

### 9.3 — Async Job Queue

- [ ] `workers/arq_settings.py` — `WorkerSettings`
- [ ] `workers/mandate_worker.py` — `async def process_payment_failed(ctx, tenant_id, payload)`
- [ ] `api/routes/webhooks.py` updated — HMAC per-tenant, ARQ enqueue, < 1s response

### 9.4 — Client Callbacks

- [ ] `services/callback_service.py` — `deliver_callback()` with `X-Aegis-Signature`, 3-attempt backoff

### 9.5 — Observability

- [ ] `observability/metrics.py` — Prometheus counters/histograms
- [ ] `observability/logging.py` — structlog JSON renderer with context vars

### 9.6 — Tier-2 Rate Limiter

- [ ] `core/tier2_rate_limiter.py` — Redis sliding window per tenant
- [ ] `tests/unit/test_rate_limiter.py` — budget, exhaustion, tenant isolation, downgrade

### 9.7 — Docker Compose

- [ ] `docker-compose.yml` updated with `redis` and `worker` services
- [ ] `.env.example` updated: `REDIS_URL`, `AEGIS_MASTER_ENCRYPTION_KEY`

### Phase 9 Acceptance Criteria

- [ ] Two tenants with different AFA thresholds produce different actions for same mandate amount
- [ ] Without auth → 401; invalid key → 403; valid key → 202
- [ ] Webhook returns 200 < 1s; ARQ job processed asynchronously
- [ ] Callback received with valid `X-Aegis-Signature`
- [ ] `GET /metrics` returns Prometheus text; `aegis_recovery_actions_total` populated
- [ ] Rate limiter downgrade confirmed in logs
- [ ] `docker compose up` starts all 4 services healthy

---

## Stretch Goal (Only if MVP dashboard fully works by Day 10)

- [ ] `synthetic/evaluator.py` — `build_atrisk_classifier()` logistic regression
- [ ] Dashboard: at-risk score column in MandateList (amber above 0.7)
- [ ] Mention in demo close: "predictive at-risk scorer"

---

*Phase numbering matches `plans/overview.md`. Full spec per phase in `plans/phase-N-*.md`.*
*Source: Master_Aegis.md Appendix A | Rewritten: 2026-08-24 | Update daily*
