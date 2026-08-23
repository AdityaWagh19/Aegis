# Task List — Aegis

> **Status:** Living document. Updated multiple times per day during the build.
> Mark `[/]` when starting a task, `[x]` when complete.
> Never delete completed items — the history is part of the BUILD_LOG.

---

## Phase 0 — Infrastructure and Data (Days 1–2: Aug 23–24)

### Repository Setup

- [x] Git repository initialized
- [x] `.git` visible (hidden attribute removed)
- [x] First commit pushed to `github.com/AdityaWagh19/Aegis`
- [x] `project-context/` directory created with all 11 documents
- [ ] `README.md` created and pushed
- [ ] `.gitignore` created (exclude `.env`, `__pycache__`, `node_modules`, `*.pyc`, `data/held_out*`)
- [ ] `.env.example` created and committed
- [ ] `compliance_config.yaml` created and committed

### Backend Skeleton

- [ ] `requirements.txt` created (fastapi, uvicorn, groq, razorpay, sqlalchemy, pydantic, pyyaml, faker, pytest, pytest-asyncio)
- [ ] `api/main.py` — FastAPI app with health check endpoint
- [ ] `models/mandate_event.py` — Pydantic `MandateEvent` model
- [ ] `models/recovery_decision.py` — Pydantic output models
- [ ] `models/db.py` — SQLAlchemy ORM table definitions
- [ ] `config/loader.py` — `compliance_config.yaml` loader
- [ ] Database migrations / table creation script

### Synthetic Data (Must complete before any rule-writing)

- [ ] `synthetic/generator.py` — generates 500 mandate events with correct distribution
  - INSUFFICIENT_FUNDS: 40%
  - BANK_TECHNICAL_DECLINE: 20%
  - MANDATE_PAUSED: 15%
  - AFA_REQUIRED: 10%
  - MANDATE_EXPIRED: 10%
  - NON_REVOCABLE_HARD_DECLINE: 5%
- [ ] `synthetic/held_out.py` — splits and locks held-out set (20% = 100 records)
- [ ] Generate and commit `data/synthetic_held_out.csv` — **do this before Day 3**
- [ ] `synthetic/evaluator.py` — `evaluate_held_out_set()` function
- [ ] Verify distribution within 5% tolerance of targets

### EC2 Setup

- [ ] EC2 instance launched (Ubuntu 22.04, t3.medium), Elastic IP assigned
- [ ] Security groups open: ports 22, 80, 443
- [ ] Docker + Docker Compose + Nginx + certbot installed
- [ ] `/home/ubuntu/Aegis/.env` created with all real values
- [ ] Nginx config created and enabled
- [ ] SSL certificate obtained via certbot
- [ ] Razorpay test Plan + Subscription created for charge simulator
- [ ] GitHub repo secrets: `EC2_HOST`, `EC2_SSH_PRIVATE_KEY`, `EC2_USERNAME`

---

## Phase 1 — Tier-1 Rule Engine (Days 3–5: Aug 25–27)

- [ ] `core/tier1_engine.py` — `classify(event) -> Tier1Result`
  - [ ] `INSUFFICIENT_FUNDS` rule (including high-bounce escalation)
  - [ ] `AFA_REQUIRED` rule (including borderline ambiguity routing)
  - [ ] `MANDATE_PAUSED` rule
  - [ ] `BANK_TECHNICAL_DECLINE` rule (including max-attempts check)
  - [ ] `NON_REVOCABLE_HARD_DECLINE` rule
  - [ ] `MANDATE_EXPIRED` rule
  - [ ] Unknown decline code → Tier-2 routing
- [ ] `tests/unit/test_tier1.py` — all 10+ test cases from `test.md`
- [ ] Verify: zero LLM imports in `core/tier1_engine.py`
- [ ] Measure: Tier-1 latency P95 < 5ms on 500 records
- [ ] Measure: Tier-1 resolves 65–75% of generated dataset

---

## Phase 2 — Tier-2 and Compliance Gate (Days 6–8: Aug 28–30)

### Tier-2 Agent

- [ ] `core/tier2_agent.py` — `tier2_reason(event) -> Tier2Result`
  - [ ] Groq client initialization
  - [ ] `SYSTEM_PROMPT` with allowed actions injected
  - [ ] `PROPOSE_RECOVERY_TOOL` function schema
  - [ ] Pydantic validation of Groq output (rejects out-of-allow-list action)
  - [ ] Fallback to `ESCALATE_TO_HUMAN` on malformed output or LLM failure
  - [ ] Hinglish message templates seeded into system prompt
- [ ] `tests/unit/test_tier2_schema.py` — schema validation tests

### Compliance Gate

- [ ] `core/compliance_gate.py` — `check(event, proposed_action) -> ComplianceResult`
  - [ ] Rule 1: Non-revocable mandate hard decline
  - [ ] Rule 2: Max retry attempts cap
  - [ ] Rule 3: AFA threshold routing
  - [ ] Rule 4: 24h pre-debit notice active
- [ ] `tests/unit/test_compliance_gate.py` — all test cases from `test.md`
  - [ ] Every rule has an activation test
  - [ ] Every rule has a pass-through test
  - [ ] Deliberate Tier-2 bypass attempt is caught

### Razorpay Integration and Mock

- [ ] `services/razorpay_client.py` — resume, pause, payment link creation
- [ ] `services/mock_notification.py` — `MockNotificationService`
- [ ] `core/action_executor.py` — routes `final_action` to correct execution path

### Batch Orchestrator

- [ ] `core/` — `process_batch(events) -> BatchResult`
- [ ] `audit/log.py` — append-only audit write

### API Routes

- [ ] `api/routes/recovery.py` — `POST /v1/recovery/batch`, `GET /v1/recovery/batch/{id}`
- [ ] `api/routes/mandates.py` — `GET /v1/mandates/{id}`
- [ ] `api/routes/metrics.py` — `GET /v1/metrics`
- [ ] `api/routes/audit.py` — `GET /v1/audit`
- [ ] `api/routes/human_review.py` — `GET /v1/human-review`
- [ ] `api/routes/webhooks.py` — `POST /webhooks/razorpay`

### Integration Test

- [ ] `tests/integration/test_batch_pipeline.py` — full pipeline with deliberate violation injection

---

## Phase 3 — Dashboard (Days 9–10: Aug 31–Sep 1)

- [ ] React app initialized in `dashboard/`
- [ ] `components/MetricCards.tsx` — Rs. recovered, recovery %, violations
- [ ] `components/TierSplitChart.tsx` — Tier-1 vs Tier-2 donut chart
- [ ] `components/RecoveryByCategoryTable.tsx` — per-category recovery rate
- [ ] `components/MandateList.tsx` — scrollable mandate table
- [ ] `components/MandateDetailDrawer.tsx` — full decision trail on click
- [ ] `components/ComplianceOverrideCard.tsx` — the demo-critical component
- [ ] `components/HinglishMessagePreview.tsx` — message preview card
- [ ] `components/HumanReviewQueue.tsx` — escalated mandates
- [ ] `components/BatchUploader.tsx` — CSV drag-and-drop with progress bar
- [ ] `api/aegis.ts` — typed API client for all endpoints
- [ ] Pages: `Dashboard.tsx`, `Batch.tsx`, `Audit.tsx`
- [ ] Manual end-to-end test: upload demo CSV, verify all dashboard components render

---

## Phase 4 — Evaluation and Polish (Day 11: Sep 2)

- [ ] Run `pytest tests/unit/ -v` — all pass
- [ ] Run `pytest tests/integration/ -v` — all pass
- [ ] Run held-out evaluation: `evaluate_held_out_set()`
  - [ ] Assert `compliance_violations_executed == 0`
  - [ ] Record honest metrics (accuracy, tier split, false escalation rate)
  - [ ] If Tier-2 rate > 30%: add more specific rules to Tier-1
- [ ] Fix any failures identified during evaluation
- [ ] Verify dashboard displays held-out metrics correctly

---

## Phase 5 — Demo and Submission (Days 12–13: Sep 3–5)

- [ ] Architecture diagram created (export from README.md Mermaid or draw.io)
- [ ] `README.md` polished (based on `dev-guide.md`)
- [ ] `project-context/progress.md` copied/renamed to `BUILD_LOG.md` for submission
- [ ] Demo script rehearsed 3+ times (following `project-context/demo.md`)
- [ ] All items in `demo.md` Pre-Demo Checklist checked
- [ ] 5-minute video recorded — compliance override moment is unmissable
- [ ] All items in `demo.md` Submission Checklist checked
- [ ] Final push to `main` — verify GitHub Actions deploy passes
- [ ] Submission completed

---

## Stretch Goal (Only if MVP dashboard fully works by Day 10)

- [ ] `synthetic/evaluator.py` — `build_atrisk_classifier()` logistic regression
  - Features: `days_since_salary_credit`, `prior_bounce_count`, `amount / AFA_threshold`, `attempt_number`
- [ ] Dashboard: add at-risk score column to MandateList
- [ ] Mention in demo close: "the predictive at-risk scorer — this converts Aegis from reactive to predictive"

---

*Source: Master_Aegis.md Appendix A, §20, §29 | Last updated: 2026-08-23 | Update daily*
