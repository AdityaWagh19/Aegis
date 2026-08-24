# Build Log — Aegis

> **Status:** Append-only. Write at the end of every build session.
> This document becomes `BUILD_LOG.md` for submission.
> Required submission artifact: genuine real failures, not sanitized retrospectives.

---

## Log Format

```
## Day N — [Date]

### Built
- [What was created or completed]

### Failures and Fixes
- [What went wrong, the error or symptom, and how it was resolved]

### Decisions Made
- [Any design decision made during implementation that was not in the master document]

### Metrics (if measured)
- [Tier-1 rate, test results, latency measurements]

### Tomorrow
- [Top 3 tasks for the next session]
```

---

## Day 1 — Aug 23

### Built

- Git repository initialized at `c:\Users\omen\OneDrive\Desktop\Aegis`
- `.git` folder made visible (hidden attribute removed via `attrib -h -s`)
- Remote origin set to `https://github.com/AdityaWagh19/Aegis.git`
- First commit: `Master_Aegis.md` (2,111 lines) pushed to `main`
- `project-context/` directory created with all 11 documentation files:
  - `context.md`, `compliance.md`, `architecture.md`, `api.md`
  - `dev-guide.md`, `test.md`, `deploy.md`, `demo.md`
  - `tasks.md`, `progress.md`, `future-plans.md`
- Documentation audit performed (`project_context_audit.md`)

### Failures and Fixes

- *(Record any failures encountered during setup here)*

### Decisions Made

- Documentation structure: 11-document `project-context/` layout adopted from audit
- `Master_Aegis.md` retained as historical design brief alongside new modular docs
- LLM provider: Groq (llama-3.3-70b-versatile) confirmed over Anthropic for free tier and low latency

### Tomorrow

- Create `.gitignore`, `.env.example`, `compliance_config.yaml`
- Initialize backend skeleton (`api/main.py`, `models/`, `config/`)
- Generate synthetic dataset and lock the held-out set before any rule-writing

---

## Day 2 — Aug 24

### Built

- Complete 9-phase engineering specification written to `plans/` directory:
  - `plans/overview.md` — master dependency graph, phase table, file index, deliverables
  - `plans/phase-1-foundation.md` through `plans/phase-5-action-executor-audit.md` — core pipeline phases
  - `plans/phase-6-api-layer.md` — FastAPI routes, CSV parsing, HMAC webhook, batch caching
  - `plans/phase-7-dashboard.md` — React 18 + TypeScript, 9 components, typed API client
  - `plans/phase-8-evaluation-submission.md` — evaluator, demo batch, pre-demo checklist
  - `plans/phase-9-production-hardening.md` — multi-tenancy, API key auth, ARQ async queue, client callbacks, Prometheus, Tier-2 rate limiter
- `project-context/architecture.md` updated with full Production Architecture section
- Cross-document audit performed — 5 Critical, 10 High, 8 Medium, 3 Low issues found and fixed
- Production integration model decided: **Model A — Sidecar**

### Failures and Fixes

- Architecture.md `replace_file_content` had minor mismatch on trailing newline — resolved by reviewing exact content before edit

### Decisions Made

- Integration model: Sidecar (Model A) over full middleware replacement — least disruption to existing NBFC systems
- Async queue: ARQ (asyncio-native) over Celery for Groq `await` compatibility
- Tenant secret storage: Fernet symmetric encryption with master key over per-secret Secrets Manager
- Tier-2 rate limiting: Redis sliding window over token bucket — matches Groq rate limit semantics
- In-memory `_batch_cache` (Phase 6) to be replaced by `batch_jobs` DB table in Phase 9

### Metrics

- Plans: 9 files, 4,214 insertions
- Architecture.md: +154 lines (production section)
- Doc audit: 26 issues identified and resolved across all docs

### Tomorrow

- Execute Phase 2: Tier-1 rule engine (`core/tier1_engine.py`) against the locked held-out set
- Target: Tier-1 resolves 60–80% of generated dataset, P95 < 5ms
- Full `tests/unit/test_tier1.py` suite from `project-context/test.md`

---

## Phase 1 Execution — Aug 24 (same day, second session)

### Built

- Full Phase 1 foundation per `plans/phase-1-foundation.md`:
  - Directory skeleton with `__init__.py` in all 11 packages (`api/`, `api/routes/`, `core/`, `services/`, `audit/`, `models/`, `config/`, `synthetic/`, `tests/`, `tests/unit/`, `tests/integration/`)
  - `requirements.txt` (15 pinned deps), `.gitignore`, `.env.example`, `compliance_config.yaml`, `docker-compose.yml`
  - `config/loader.py` — Pydantic v2 `ComplianceConfig` + cached `load_config()` / FastAPI `get_config()` dependency
  - `models/mandate_event.py` — canonical `MandateEvent` input schema (UUID-on-empty mandate_id, optional `correct_action` ground-truth field per D2)
  - `models/recovery_decision.py` — `ComplianceResult`, `Tier1Result`, `Tier2Result`, `RecoveryDecision`, `BatchMetrics`, `BatchResult`, `EvaluationResult`
  - `models/db.py` — async SQLAlchemy ORM (`mandate_events`, `recovery_decisions`, `audit_log`, `human_review_queue`) + `init_db()`
  - `synthetic/generator.py` — seeded (42) generator, distribution mirroring config, internal held-out split
  - `synthetic/evaluator.py` — `load_held_out_events()` + `evaluate_held_out_set()` skeleton (Phase 8)
- Synthetic data generated and **held-out set locked before any rule-writing**: commit `7cea696` ("data: generate and lock held-out evaluation set")
- Python 3.12.1 venv at `.venv/`; all pinned requirements installed cleanly

### Failures and Fixes

- **`audit_log.entry_id` autoincrement broken on SQLite** — `BigInteger` primary keys are not rowid aliases in SQLite, so inserts without explicit `entry_id` failed with `NOT NULL constraint failed`. Caught proactively by an insert test before any Phase 5 code exists. Fixed with `BigInteger().with_variant(Integer, "sqlite")` (BIGINT preserved on PostgreSQL, INTEGER rowid alias on SQLite). Re-tested: auto-generated ids `[1, 2]`.
- **Held-out set overwritten by a validation re-run of the generator** — re-running `python -m synthetic.generator` after the lock commit rewrote `data/synthetic_held_out.csv`: `random.seed(42)` makes category draws deterministic, but event `timestamp` uses wall-clock `datetime.now()`, so regenerated files are never byte-identical. Caught via `git status` showing the file modified; fixed by `git restore data/synthetic_held_out.csv` (committed version is authoritative). Lesson recorded: the generator must NOT be run again now that the held-out set is locked; if regeneration is ever required, derive timestamps from the seeded RNG first and re-lock.
- Docker is not installed on the build machine — `docker compose config` could not run locally. Compose file validated via YAML parse + structural assertions instead; must re-validate on the EC2 target.

### Decisions Made

- Held-out set committed as a standalone commit immediately after generation, so its timestamp precedes any future `core/` commits (risk-table mitigation from the phase plan).
- tasks.md items that contradict the engineering spec were annotated rather than silently checked: `api/main.py` → Phase 6, Alembic → Phase 9, EC2 → deployment track (`deploy.md`).

### Metrics

- `data/synthetic.csv`: 500 rows, all 14 fields populated; distribution deltas vs targets: INSUFFICIENT_FUNDS −0.014, BANK_TECHNICAL_DECLINE +0.014, MANDATE_PAUSED +0.020, AFA_REQUIRED −0.014, MANDATE_EXPIRED +0.008, NON_REVOCABLE_HARD_DECLINE −0.014 (all within ±5%)
- `data/synthetic_held_out.csv`: exactly 100 unique records (+1 header = 101 lines); category coverage: IF=47, BTD=18, MP=16, AE=8, AFA=9, NRHD=2
- All 6 validation steps from the phase plan pass; all 10 acceptance criteria satisfied

### Notes for Next Session

- NON_REVOCABLE_HARD_DECLINE has only 2 held-out records (plan estimated ~5). Seed is locked and data committed — do NOT regenerate. Phase 8 false-escalation metrics will be thin for this category; report honestly.
- Tier-1 engine must not peek at `correct_action`; evaluator checks `correct_action is not None`.

### Tomorrow

- *(Superseded by Phase 2 tasks above)*

---

## Phase 2 Execution — Aug 24 (same day, third session)

### Built

- `core/tier1_engine.py` — deterministic rule engine per plans/phase-2-tier1-rule-engine.md Task 2.1: all six taxonomy codes, contextual overrides (high-bounce escalation, late-cycle ambiguity, AFA borderline band, ENACH/UPI retry caps), unknown-code safety net. Zero LLM imports.
- `tests/unit/test_tier1.py` — 17 tests covering every rule, edge case, and the no-LLM invariant (Task 2.2)
- `scripts/measure_tier1.py` — resolution-rate and latency measurement over the 500-record synthetic batch (Task 2.3)
- `.env` created with validated Groq/Razorpay test credentials; Groq model IDs replaced with live-catalog equivalents (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) after discovering the plan's pinned models no longer exist on Groq

### Failures and Fixes

- **`Tier1Result.action: str` rejected `None`** — Phase 2's D2 requires `action=None` for ambiguous cases, but the Phase 1 Pydantic model declared `action: str`. Fixed by widening to `Optional[str] = None` in `models/recovery_decision.py`. One-line type change, required to unblock the engine.
- **`test_tier1_has_no_llm_imports` false positive** — the plan's substring scan flagged the word "groq" inside tier1_engine's own docstring ("must never import from ... groq ..."). Plan's two files contradicted each other. Fixed by switching the test to AST-based import extraction (`ast.walk` → Import/ImportFrom nodes) — stronger enforcement, no comment/docstring false positives.
- **`mock.patch("core.tier2_agent")` raised ModuleNotFoundError** — module doesn't exist until Phase 4. Added `create=True` so the invariant test passes now and remains valid once Phase 4 lands; also added `assert_not_called()` from test.md's version.
- **`python scripts/measure_tier1.py` ModuleNotFoundError** — direct script invocation doesn't put repo root on sys.path. Added a two-line `sys.path` bootstrap so the plan's documented invocation works.

### Decisions Made

- Resolution rate measured at **83.8%**, above the 60–80% acceptance window. The phase plan's risk table explicitly deems >80% "acceptable — but check that ambiguous routing logic is not suppressed". Ran a reason-level breakdown: all three dataset-reachable ambiguous branches fire (late_cycle_insufficient_funds=72, afa_below_threshold_inconsistency=8, borderline_afa=1; total 81 = exact ambiguous count). `unknown_decline_code` is unreachable in synthetic data (generator emits only known codes) and is covered by unit tests. Rules were NOT tuned to move the number.
- Measurement runs on all 500 rows of data/synthetic.csv per the plan's script (held-out rows included in this dev-time metric only; held-out set itself untouched).

### Metrics

- `pytest tests/unit/test_tier1.py -v`: **17 passed**, 0 failures
- Import check: `import core.tier1_engine` → no LLM imports
- Resolution: **419/500 resolved (83.8%)**, 81 ambiguous (16.2%) → well within the ≤30% Tier-2 ceiling (P1)
- Latency: 500 sequential classify() calls in ~1.2ms total → P95 per record ≈ 0.00ms (< 5ms target)

### Tomorrow

- Execute Phase 3: compliance gate (`core/compliance_gate.py`) + its critical unit suite

---

## Phase 3 Execution — Aug 24 (same day, fourth session)

### Built

- `core/compliance_gate.py` — `ComplianceGate` class per plans/phase-3-compliance-gate.md Task 3.1: four rules in severity order (non-revocable > max-retry > AFA > 24h notice), first-violation-wins, config injected at construction, redirects per D5 (`ESCALATE_TO_HUMAN` / `SEND_UPI_INTENT_PUSH` / `SEND_HINGLISH_NUDGE`), never returns `final_action=None`.
- `tests/unit/test_compliance_gate.py` — 24 tests: activation + pass-through per rule, rule-1 scope check (revocable mandate with NON_REVOCABLE code not blocked), SIP vs general AFA threshold selection, non-retry actions exempt from retry caps, full 6-code × 7-action `final_action is not None` sweep.

### Failures and Fixes

- **Same plan bug as Phase 2, caught pre-emptively** — `test_compliance_gate_has_no_tier_imports` substring-scans source for "tier1_engine"/"tier2_agent", which appear in the gate module's own INVARIANTS docstring. Applied the identical AST import-extraction fix used in Phase 2 before running the suite; passed first try. (Considered patching the docstring instead, but the AST test is strictly stronger and the docstring documents a real invariant worth keeping.)

### Decisions Made

- Kept the plan's Rule 1 scope note verbatim in code comments: the rule triggers only when `is_revocable=False AND decline_code == NON_REVOCABLE_HARD_DECLINE`. Documented alternative (`if not event.is_revocable:`) stays available if broader protection is ever required.
- Test count is 24 (plan deliverable text said "25+"); the plan's own Task 3.2 defines exactly 24 and covers every activation/pass-through pair — implemented exactly, count recorded honestly.

### Metrics

- `pytest tests/unit/test_compliance_gate.py -v`: **24 passed**, 0 failures
- Full unit suite after Phase 2+3: **41 passed**, 0 failures
- Tier-1 regression measurement unchanged: 83.8% resolved, P95 ≈ 0.00ms
- Gate purity: no DB/filesystem/network access; only injected `ComplianceConfig`

### Tomorrow

- Execute Phase 4: Tier-2 Groq agent (`services/groq_client.py`, `core/tier2_agent.py`) with schema-validation tests

---

## Phase 4 Execution — Aug 24 (same day, fifth session)

### Built

- `services/groq_client.py` — lazy singleton `AsyncGroq`; `load_dotenv()` at module import (nothing loaded `.env` before this); `get_groq_fallback_client()` exposing the second Groq key for later degradation logic
- `core/tier2_agent.py` — `RECOVER_MANDATE_TOOL` schema, seeded `SYSTEM_PROMPT` (taxonomy + compliance rules + 3 Hinglish examples), async `tier2_reason()` with forced tool choice, no-tool-call guard, Pydantic enforcement, four-branch fallback to `ESCALATE_TO_HUMAN`
- `tests/unit/test_tier2_schema.py` — 8 tests, fully mocked (no live API)
- `scripts/smoke_test_tier2.py` — live connectivity/quality check with latency timing
- Docs synced: `.env.example` (fallback key var, verified model IDs, `sqlite+aiosqlite` default), dev-guide model table rewritten for the live Groq catalog

### Failures and Fixes

- **`APIError(...)` signature mismatch** — plan's test constructed `APIError("Rate limit", response=..., body=...)`, but groq 0.9.0's signature is `APIError(message, request, *, body)`. Fixed test construction with a real `httpx.Request`.
- **Smoke script duplicate-kwarg TypeError** — plan's Task 4.6 hardcodes `days_since_salary_credit=5` while TEST_CASES[0] also passes it → Python rejects duplicate keyword. Fixed by merging base dict with per-case overrides.
- **Plan's pinned models dead** — `llama-3.3-70b-versatile` etc. absent from Groq's 2026 catalog (discovered during credential validation earlier today). `.env` and all defaults now use verified `openai/gpt-oss-120b` / `gpt-oss-20b`.

### Decisions Made

- `GROQ_API_KEY_FALLBACK` is exposed via `get_groq_fallback_client()` but deliberately NOT auto-retried inside `tier2_reason()` — that would change the tested AC semantics ("API error → ESCALATE_TO_HUMAN"). Key-level degradation belongs to the Phase 9 Tier-2 rate limiter per plans/overview.md.
- Added `test_tier2_fallback_on_malformed_output` (from test.md/tasks.md AC) exercising the `json.JSONDecodeError` branch; suite now matches the stated deliverable count of 8.
- Smoke script measures per-call latency (needed to validate the <3000ms AC).

### Metrics

- `pytest tests/unit/test_tier2_schema.py -v`: **8 passed**, 0 failures (no API calls)
- Live smoke (primary key, gpt-oss-120b):
  - INSUFFICIENT_FUNDS late-cycle → SCHEDULE_POST_SALARY, conf 0.95, correct Hinglish
  - AFA_REQUIRED borderline (Rs. 14,200) → SEND_UPI_INTENT_PUSH, conf 0.98, loss-aversion framing
  - NON_REVOCABLE_HARD_DECLINE → ESCALATE_TO_HUMAN, conf 0.99, no customer message (correct)
  - Latency: 1645 / 815 / 1089 ms → avg **1183ms** (< 3000ms target)

### Tomorrow

- Execute Phase 5: action executor, Razorpay client, audit log, orchestrator (`process_batch()`)

---

## Phase 5 Execution — Aug 24 (same day, sixth session)

### Built

- `services/razorpay_client.py` — test-mode-only Razorpay wrappers (`rzp_test_` prefix enforced at init; sync SDK wrapped in `run_in_executor`)
- `services/mock_notification.py` — WhatsApp/SMS stub writing `notification_log.jsonl`
- `core/action_executor.py` — 7-action dispatch with no fallthrough; unknown action raises `ValueError`; API failures → outcome `"failed"`
- `audit/log.py` — append-only `AuditLog` (only `append()` exists), full decision payload per entry
- `core/orchestrator.py` — `process_batch()`: Tier-1 → (Tier-2) → Gate → Executor → Audit, plus human-review queue writes and inline metrics
- `tests/conftest.py` — integration tests isolated on `aegis_test.db` (set before models.db import; session-scoped create/cleanup) per the plan's risk table
- `tests/integration/test_batch_pipeline.py` — 3 tests: tier-split window, deliberate non-revocable violation caught + never executed, one audit row per mandate
- `scripts/smoke_test_pipeline.py` — live end-to-end batch through the real stack

### Failures and Fixes

- **`ModuleNotFoundError: pkg_resources`** — razorpay 1.4.1 imports `pkg_resources`; Python 3.12 venvs ship without setuptools and setuptools ≥81 removed the module. Fixed by installing/pinning `setuptools<81` in requirements.txt (documented as a razorpay transitive requirement).

### Decisions Made

- Live smoke revealed two genuine platform facts, recorded for the demo: (1) **Razorpay test mode does not support UPI payment links** ("not supported in Test Mode") — intent-push outcomes are `failed` in test mode but will work on live mode; (2) subscription resume/pause on synthetic mandate ids 404 → outcome `failed`, which exercises the executor's error path honestly.
- `HumanReviewQueue.reason` falls back to `"tier2_escalation"` when escalation came from Tier-1 directly (no compliance rule involved) — per plan code, kept as-is.
- SQLite does not enforce FK constraints by default: orchestrator intentionally never inserts `MandateEventORM` rows, so review-queue/decision FKs to `mandate_events` would fail on PostgreSQL if events aren't persisted first. Noted as a production-deploy consideration (Phase 9/EC2); harmless on SQLite dev.

### Metrics

- Integration suite: **3/3 passed**; full suite: **52/52 passed**
- Live pipeline batch (6 events): tier1=4 (66.7%), tier2=2; renewal-link payment link **executed** on Razorpay test mode; nudge mocked; NRHD escalated + queued; violations caught=0, executed=0
- audit_log: exactly 6 rows (entry_id autoincrement 1–6 — Phase 1 PK fix validated); human_review_queue: 1 row
- Tier-1 regression unchanged: 83.8% resolved, P95 ≈ 0.00ms

### Tomorrow

- Execute Phase 7: React dashboard consuming these endpoints

---

## Phase 7 Planning Session — Aug 24 (same day, eighth session)

### Built

- `project-context/design.md` — consolidated design system from the four root schema files (`DESIGN.md`, `tokens.json`, `variables.css`, `theme.css`): token tables (colors, surfaces, elevation), sanctioned semantic status extension (§2.3), typography with font-sourcing rule (Roobert → self-hosted Inter Tight under the display token), spacing/radius/shadows, component specs, voice/content rules, accessibility floor, and the full Phase 7 frontend architecture (route map, three layouts, per-page content specs)
- `plans/phase-7-dashboard.md` revised: scope now covers 6 routes (`/`, `/docs`, `/login`, `/app`, `/app/batch`, `/app/audit`) across three layouts + demo auth gate; new tasks 7.0/7.10a–e; restyling rule maps all legacy hardcoded hexes in component sketches to tokens; validation + ACs extended accordingly
- `project-context/tasks.md` Phase 7 checklist rewritten to match
- Toolchain verified: Node v22.7.0 / npm 10.8.2 available for Vite build

### Decisions Made

- **Semantic status colors are a documented, bounded extension** of the single-accent palette: success/warning/danger/info appear only as text/icon/tint treatments for outcome meaning — never fills, never headlines. Without them a payments-recovery console cannot communicate state; with the bound, the editorial restraint survives.
- **Roobert is commercial** — display token keeps the name but loads Inter Tight (the reference's own sanctioned substitute) via Fontsource; body stays Inter.
- **Auth is a demo gate**: localStorage session + redirect guard on `/app/*`; login copy and sidebar disclose that API-key auth lands in Phase 9. Route structure won't change when real auth arrives.
- Page count frozen at six routes (+drawer) to prevent scope creep; new pages require a plan amendment.

### Metrics

- Docs: design.md ~230 lines; phase-7 plan +~120 lines of revisions; tasks.md Phase 7 rewritten

### Tomorrow

- Execute Phase 7 implementation per revised plan

---

## Phase 7 Execution — Aug 24 (same day, ninth session)

### Built

- Complete `dashboard/` React 18 + TypeScript app on Vite 8 + Tailwind v4, styled exclusively with design-system tokens (`src/styles/theme.css` = schema tokens + sanctioned status extensions; pixel-named spacing steps override TW defaults — use only defined steps)
- Router: `/` Landing · `/docs` Docs · `/login` Login · `/app` Overview · `/app/batch` Batches · `/app/audit` Audit trail; three layouts (Marketing/Auth/AppShell) with demo AuthGuard + sign out
- All 9 core components per spec: MetricCards (ink values + semantic context lines), TierSplitChart (soot+sky-wash donut with printed counts), RecoveryByCategoryTable, MandateList (tier/outcome badges, ⚠ flags, keyboard rows), MandateDetailDrawer (proposal→gate→final flow, confidence bar, alternatives chips, Razorpay JSON collapse), ComplianceOverrideCard (warning tint, struck proposal, cited rule), HinglishMessagePreview, HumanReviewQueue (resolve wired), BatchUploader (3 states, honest timing copy)
- Landing with real product copy (no lorem ipsum): hero + single highlight span, floating preview mock with working tab pills, how-it-works trio, six failure categories grid, compliance promise block, soot footer
- Docs page: anchor sidebar; compliance rules table; CSV column dictionary; all seven endpoints with curl examples; allow-list grid
- Login: email/passphrase form + guest path, inline validation hints, plain disclosure that auth is a local demo gate until Phase 9
- lib/format.ts (en-IN rupees, humanized actions/outcomes); lib/auth.ts (localStorage session)

### Failures and Fixes

- **create-vite template shipped broken TS config** — no `"jsx"` compilerOption → every JSX file errored. Fixed tsconfig.json (`jsx: react-jsx`, strict, DOM.Iterable).
- **Template omitted react/react-dom/@types entirely** — recharts had pulled react@19 transitively. Installed react@18 + react-dom@18 + @types/react@18 per plan's React-18 decision.
- **npm optional-deps bug (rolldown native binding)** — `@rolldown/binding-win32-x64-msvc` skipped on install; clean reinstall didn't help. Installed the binding explicitly.
- **Same for @vitejs/plugin-react** — absent from template deps AND latest 4.x peers vite ≤7 while template installed vite 8; resolved by installing @vitejs/plugin-react@6 (peers vite ^8).

### Decisions Made

- Dashboard Overview deliberately does NOT render rupee totals: the all-time /metrics endpoint carries counts, not rupees — fabricating numbers in UI would violate honesty-first. Rupee MetricCards appear only on Batches view where real batch data exists.
- MandateList drops the planned "Decline Code" column: RecoveryDecision objects carry no decline_code field; showing "(see detail)" filler was worse than an honest column cut. Codes remain visible via drawer rationale and audit rows.
- Chart palette kept strictly monochrome (soot/sky-wash slices) per design system; outcome semantics live in badges only.

### Metrics

- `npm run build`: ✓ type-check + bundle green (~5s; one chunk-size warning from recharts — acceptable for demo)
- Dev server: all six routes HTTP 200
- Live integration through the exact API path the UI drives: upload demo_10.csv → 202 (10 records, tier1=8/tier2=2, violations caught=6/executed=0) → poll 200 → human-review 5 items
- Full backend regression untouched: 52/52 tests still passing

### Tomorrow

- One manual browser QA pass over the six routes (the only open AC items), then Phase 8 evaluation

---

## Phase 6 Execution — Aug 24 (same day, seventh session)

### Built

- `api/main.py` — FastAPI app with lifespan (`init_db()` at startup), CORS from `ALLOWED_ORIGINS`, `/health`, all 7 routers registered
- `api/routes/recovery.py` — CSV upload (parse-in-route per D3, inline `await process_batch()` per D2), `_batch_cache` polling endpoint (Phase 9 migration target noted in code)
- `api/routes/mandates.py`, `metrics.py` (DB-aggregated per D6), `audit.py` (paginated), `human_review.py` (+ resolve POST), `webhooks.py` (HMAC-SHA256 verified)
- Zero business logic in routes — every handler delegates to `core/`

### Failures and Fixes

- **Plan bug: inverted `is_held_out` parsing** — recovery.py compared `.lower() == "false"`, marking every row held-out. Fixed to `== "true"` (no pipeline impact today; field is informational).
- **Plan bug: missing import** — audit.py used `func.count` but never imported `func` → would NameError on first `/audit` request. Added to the import line.
- **Webhook "500" during smoke** — PowerShell quote-stripping mangled the JSON body identically for signer and sender, so HMAC passed but `json.loads` failed. Test-harness artifact, not an app bug; retested correctly via `--data-binary @file`. Observation recorded: a valid-signature + malformed-JSON body returns 500 — acceptable while Razorpay only sends well-formed signed payloads; harden if webhook retries become an issue.

### Decisions Made

- Kept plan's `_batch_cache` design (D5's DB-reconstruction description is superseded by Task 6.2's actual code); Phase 9 replaces it with `batch_jobs`.
- `data/demo_10.csv` regenerated on demand (`head -11 data/synthetic.csv > data/demo_10.csv`) rather than committed — it contains rows derived from held-out records; avoids duplicating eval data in another artifact.

### Metrics (live server run, port 8000)

- Boot: uvicorn started clean; `GET /health` → `{"status":"ok","service":"aegis"}`
- `POST /api/v1/recovery/batch` (demo_10.csv): **HTTP 202**, batch_id returned, record_count=10, parse_errors=[], tier split 8/2 (80.0%), violations caught=6 / executed=0
- `GET /recovery/batch/{id}` → 200, 10 decisions · `GET /metrics` → total=16, violations_executed=0, recovery_by_category populated
- `GET /audit?page=1&page_size=3` → paginated JSON (total=16) · `GET /human-review` → 3 items incl. one `max_retry_attempts_exceeded_2`
- Webhook: no signature → **403** JSON; valid HMAC-SHA256 → **200** received/ignored
- CORS: `access-control-allow-origin: http://localhost:3000` present on preflight and GET
- 404/422 paths return JSON (`{"detail": ...}`), not HTML
- Regression after API layer: **52/52 tests pass**

### Tomorrow

- Execute Phase 7: React dashboard consuming these endpoints

---

## Day 3 — Aug 25

### Built

- *(Fill in at end of session)*

### Failures and Fixes

- *(Fill in at end of session)*

### Decisions Made

- *(Fill in at end of session)*

### Metrics

- *(Fill in at end of session)*

### Tomorrow

- *(Fill in at end of session)*

---

## Day 4 — Aug 26

*(Append at end of session)*

---

## Day 5 — Aug 27

*(Append at end of session)*

---

## Day 6 — Aug 28

*(Append at end of session)*

---

## Day 7 — Aug 29

*(Append at end of session)*

---

## Day 8 — Aug 30

*(Append at end of session)*

---

## Day 9 — Aug 31

*(Append at end of session)*

---

## Day 10 — Sep 1

*(Append at end of session)*

---

## Day 11 — Sep 2 (Evaluation Day)

### Evaluation Results

*(Fill in after running `evaluate_held_out_set()`)*

```
Held-out set size:
Accuracy:
Tier-1 resolution rate:
Tier-2 resolution rate:
False escalation rate:
Compliance violations caught:
Compliance violations executed:   <-- Must be 0
```

*(Append other notes at end of session)*

---

## Day 12 — Sep 3 (Demo Day)

*(Append at end of session)*

---

## Day 13 — Sep 4–5 (Submission Buffer)

*(Append at end of session)*

---

*This document is append-only. Do not edit past entries.*
*Source: Master_Aegis.md Appendix B ("BUILD_LOG.md with genuine real failures") | Started: 2026-08-23*
