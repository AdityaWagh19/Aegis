# Implementation Overview — Aegis

> **Status:** Engineering specification. Read this file before reading any phase plan.
> Phases are strictly ordered by dependency. Do not begin a phase until its predecessor's acceptance criteria are fully satisfied.

---

## Phase Breakdown Rationale

The implementation is broken into 9 phases using the following principles:

1. **Data before logic.** Synthetic data and the held-out set must be generated and locked before any rule is written (Phase 1). Contaminating the evaluation set by writing rules first is the single most damaging error in the build.
2. **Deterministic before probabilistic.** The compliance gate (Phase 3) is built before the LLM agent (Phase 4). The gate must be fully tested in isolation before any LLM output is routed through it.
3. **Core engine before API.** Phases 2–5 complete the entire processing pipeline as a callable Python library. Phase 6 wraps it in FastAPI. This allows the pipeline to be unit- and integration-tested before any HTTP layer exists.
4. **Backend before frontend.** The dashboard (Phase 7) consumes the API; it has no logic of its own. There is no value building it until the API returns correct data.
5. **Evaluation before hardening.** Phase 8 runs the held-out evaluation and produces the demo. Phase 9 then layers production capabilities (multi-tenancy, auth, async queue, observability, rate limiting) on top of the proven MVP. This ordering means the demo always has a working baseline, regardless of Phase 9 completion.
6. **Infrastructure last.** Phase 9 adds no new pipeline logic. It wraps the existing `process_batch()` / `process_single()` functions with production infrastructure. None of Phases 1–7 change.

---

## Dependency Graph

```
Phase 1: Foundation
    |
    +---> Phase 2: Tier-1 Rule Engine
    |         |
    |         +---> Phase 5: Action Executor + Audit
    |         |         |
    +---> Phase 3: Compliance Gate
    |         |
    |         +---> Phase 5: Action Executor + Audit
    |         |
    +---> Phase 4: Tier-2 Groq Agent
              |
              +---> Phase 5: Action Executor + Audit
                        |
                        +---> Phase 6: API Layer
                                  |
                                  +---> Phase 7: Dashboard
                                            |
                                            +---> Phase 8: Evaluation + Submission
                                                      |
                                                      +---> Phase 9: Production Hardening
                                                            (multi-tenancy, auth, async queue,
                                                             client callbacks, observability,
                                                             Tier-2 rate limiter)
```

Phases 2, 3, and 4 all depend only on Phase 1 and can be executed in sequence (2 → 3 → 4) to minimize context-switching. Phase 5 requires all three to be complete.

---

## Phase Summary

| Phase | Name | Duration Estimate | Depends On | Ends With |
|---|---|---|---|---|
| 1 | Foundation | Day 1–2 | — | Locked held-out set, all models, DB tables created, synthetic CSV generated |
| 2 | Tier-1 Rule Engine | Day 3–4 | Phase 1 | Full unit tests passing, < 5ms P95, 60–80% resolution confirmed |
| 3 | Compliance Gate | Day 5 | Phase 1 | All 4 rules unit-tested, pure function proven, no LLM deps |
| 4 | Tier-2 Groq Agent | Day 6–7 | Phase 1 | Structured output validated, Hinglish drafting working, fallback proven |
| 5 | Action Executor + Audit | Day 8–9 | Phase 2, 3, 4 | Full `process_batch()` callable, Razorpay test calls working, audit log append-only |
| 6 | API Layer | Day 9–10 | Phase 5 | All endpoints returning correct data, integration tests passing |
| 7 | Dashboard | Day 10–11 | Phase 6 | All components rendering, compliance override card visible, CSV upload working |
| 8 | Evaluation + Submission | Day 12–13 | Phase 7 | `compliance_violations_executed == 0` asserted, demo recorded, submission complete |
| 9 | Production Hardening | Day 14–18 | Phase 8 | Multi-tenant auth, async webhook queue, client callbacks, Prometheus metrics, Tier-2 rate limiter — all validated |

---

## Implementation Order Justification

**Why Phase 3 (Compliance Gate) before Phase 4 (Tier-2 Agent)?**
The gate must have 100% passing unit tests before any LLM output is ever routed through it. If the gate is built concurrently with Tier-2, there is a risk of integration bugs that are hard to attribute. Building and testing the gate in isolation guarantees it is correct before it receives any LLM-generated action.

**Why Phase 5 (Action Executor) builds `process_batch()` rather than individual components?**
The batch orchestrator is the first integration point between Tier-1, Tier-2, and the Gate. Building it in Phase 5 forces the three independent modules to be wired together in a controlled environment — before any HTTP routing exists. Integration bugs surface at the `process_batch()` level, not during a live API request.

**Why Phase 6 (API) does not contain any business logic?**
All processing logic lives in `core/`. The API layer is a thin wrapper: parse request → call `process_batch()` → return result. This keeps the API independently replaceable (CLI, Celery worker, etc.) without touching the pipeline.

---

## Progress Tracking

Mark phase status using the following states in this document:

| Symbol | Meaning |
|---|---|
| `[ ]` | Not started |
| `[/]` | In progress |
| `[x]` | Complete — all acceptance criteria satisfied |
| `[!]` | Blocked — dependency not met or acceptance criteria failing |

### Current Status

- [x] Phase 1: Foundation
- [x] Phase 2: Tier-1 Rule Engine
- [x] Phase 3: Compliance Gate
- [x] Phase 4: Tier-2 Groq Agent
- [x] Phase 5: Action Executor + Audit
- [x] Phase 6: API Layer
- [/] Phase 7: Dashboard *(implementation complete, build green; final visual QA pass pending)*
- [/] Phase 8: Evaluation + Submission *(evaluation done — 0 violations executed; demo video + submission pending user)*
- [ ] Phase 9: Production Hardening
- [ ] Phase 10: Real-Money End-to-End Demo

---

## File Index

### Phase 1 outputs
- `requirements.txt`
- `.gitignore`
- `.env.example`
- `compliance_config.yaml`
- `docker-compose.yml`
- `models/mandate_event.py`
- `models/recovery_decision.py`
- `models/db.py`
- `config/loader.py`
- `synthetic/generator.py`
- `synthetic/evaluator.py`
- `data/synthetic.csv` (generated, committed)
- `data/synthetic_held_out.csv` (generated, committed, never overwritten)

### Phase 2 outputs
- `core/tier1_engine.py`
- `tests/unit/test_tier1.py`

### Phase 3 outputs
- `core/compliance_gate.py`
- `tests/unit/test_compliance_gate.py`

### Phase 4 outputs
- `core/tier2_agent.py`
- `tests/unit/test_tier2_schema.py`

### Phase 5 outputs
- `services/razorpay_client.py`
- `services/mock_notification.py`
- `core/action_executor.py`
- `audit/log.py`
- `core/orchestrator.py` (contains `process_batch()`)
- `tests/integration/test_batch_pipeline.py`

### Phase 6 outputs
- `api/main.py`
- `api/routes/recovery.py`
- `api/routes/mandates.py`
- `api/routes/metrics.py`
- `api/routes/audit.py`
- `api/routes/human_review.py`
- `api/routes/webhooks.py`

### Phase 7 outputs
- `dashboard/` (full React app)

### Phase 8 outputs
- `BUILD_LOG.md` (copy of `project-context/progress.md`)
- Updated `README.md`
- Demo video (external artifact)

### Phase 9 outputs
- `models/tenant.py`
- `models/db.py` (updated — 3 new tables: `tenants`, `tenant_compliance_configs`, `batch_jobs`; `tenant_id` column on existing tables)
- `api/middleware/auth.py`
- `api/middleware/__init__.py`
- `workers/mandate_worker.py`
- `workers/arq_settings.py`
- `workers/__init__.py`
- `services/callback_service.py`
- `services/razorpay_client.py` (updated — per-tenant credential injection)
- `core/tier2_rate_limiter.py`
- `core/orchestrator.py` (updated — `process_single_with_config()`)
- `core/tier2_agent.py` (updated — rate limiter integration, tenant_id label)
- `observability/metrics.py`
- `observability/logging.py`
- `observability/__init__.py`
- `docker-compose.yml` (updated — adds `redis` and `worker` services)
- `scripts/create_tenant.py`
- `scripts/set_tenant_razorpay.py`
- Updated `.env.example` (adds `AEGIS_MASTER_ENCRYPTION_KEY`, `REDIS_URL`)
- `tests/unit/test_auth_middleware.py`
- `tests/unit/test_rate_limiter.py`
- `tests/integration/test_tenant_pipeline.py`

---

## Overall Deliverables

### Phase 8 (Demo Submission)

At the end of Phase 8, the following must all be true:

1. `pytest tests/unit/ -v` — all pass, zero failures
2. `pytest tests/unit/test_compliance_gate.py -v` — all pass
3. `pytest tests/integration/ -v` — all pass
4. Held-out evaluation: `compliance_violations_executed == 0` asserted programmatically
5. Tier-1 resolution rate on held-out set: between 60% and 80%
6. Dashboard accessible at the deployed URL showing Rs. recovered / at risk, tier split, and at least one compliance override card
7. `BUILD_LOG.md` exists in repo root with at least 8 daily entries
8. 5-minute demo video following `project-context/demo.md` script, uploaded to submission platform
9. `compliance_config.yaml`, `.env.example`, and all unit tests committed to `main`

### Phase 9 (Production Prototype)

At the end of Phase 9, additionally:

10. Two tenants with different `afa_threshold_general` produce different actions for the same mandate amount — verified by test
11. `POST /api/v1/recovery/batch` without auth header → `401`; with invalid key → `403`; with valid key → `202`
12. `POST /webhooks/razorpay` returns `200` in < 1 second and enqueues a Redis job
13. ARQ worker processes the job and writes `RecoveryDecision` to DB without blocking the API process
14. Client callback received at registered `webhook_url` with valid `X-Aegis-Signature` header
15. `GET /metrics` returns Prometheus text format with `aegis_recovery_actions_total` populated per tenant
16. Tier-2 rate limiter downgrade confirmed in logs when primary budget exhausted
17. `docker compose up` starts `api`, `worker`, `db`, `redis` — all healthy

---

*Refer to each phase plan for the full engineering specification of that phase.*
*This document is updated as phases are completed.*
