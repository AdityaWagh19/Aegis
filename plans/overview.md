# Implementation Overview — Aegis

> **Status:** Engineering specification. Read this file before reading any phase plan.
> Phases are strictly ordered by dependency. Do not begin a phase until its predecessor's acceptance criteria are fully satisfied.

---

## Phase Breakdown Rationale

The implementation is broken into 8 phases using the following principles:

1. **Data before logic.** Synthetic data and the held-out set must be generated and locked before any rule is written (Phase 1). Contaminating the evaluation set by writing rules first is the single most damaging error in the build.
2. **Deterministic before probabilistic.** The compliance gate (Phase 3) is built before the LLM agent (Phase 4). The gate must be fully tested in isolation before any LLM output is routed through it.
3. **Core engine before API.** Phases 2–5 complete the entire processing pipeline as a callable Python library. Phase 6 wraps it in FastAPI. This allows the pipeline to be unit- and integration-tested before any HTTP layer exists.
4. **Backend before frontend.** The dashboard (Phase 7) consumes the API; it has no logic of its own. There is no value building it until the API returns correct data.
5. **Evaluation last.** Phase 8 runs the held-out evaluation, prepares submission artifacts, and freezes the demo. Nothing is modified after this phase without a documented reason.

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
```

Phases 2, 3, and 4 all depend only on Phase 1 and can be executed in sequence (2 → 3 → 4) to minimize context-switching. Phase 5 requires all three to be complete.

---

## Phase Summary

| Phase | Name | Duration Estimate | Depends On | Ends With |
|---|---|---|---|---|
| 1 | Foundation | Day 1–2 | — | Locked held-out set, all models, DB tables created, synthetic CSV generated |
| 2 | Tier-1 Rule Engine | Day 3–4 | Phase 1 | Full unit tests passing, < 5ms P95, 65–75% resolution confirmed |
| 3 | Compliance Gate | Day 5 | Phase 1 | All 4 rules unit-tested, pure function proven, no LLM deps |
| 4 | Tier-2 Groq Agent | Day 6–7 | Phase 1, 3 | Structured output validated, Hinglish drafting working, fallback proven |
| 5 | Action Executor + Audit | Day 8–9 | Phase 2, 3, 4 | Full `process_batch()` callable, Razorpay test calls working, audit log append-only |
| 6 | API Layer | Day 9–10 | Phase 5 | All endpoints returning correct data, integration tests passing |
| 7 | Dashboard | Day 10–11 | Phase 6 | All components rendering, compliance override card visible, CSV upload working |
| 8 | Evaluation + Submission | Day 12–13 | Phase 7 | `compliance_violations_executed == 0` asserted, demo recorded, submission complete |

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

- [ ] Phase 1: Foundation
- [ ] Phase 2: Tier-1 Rule Engine
- [ ] Phase 3: Compliance Gate
- [ ] Phase 4: Tier-2 Groq Agent
- [ ] Phase 5: Action Executor + Audit
- [ ] Phase 6: API Layer
- [ ] Phase 7: Dashboard
- [ ] Phase 8: Evaluation + Submission

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
- `synthetic/held_out.py`
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

---

## Overall Deliverables

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

---

*Refer to each phase plan for the full engineering specification of that phase.*
*This document is updated as phases are completed.*
