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

- Execute Phase 1: project skeleton, Pydantic models, DB schema, SQLite setup
- Generate synthetic dataset (500 records) and lock held-out set before writing any Tier-1 rules
- Create `.gitignore`, `.env.example`, `compliance_config.yaml`, `requirements.txt`

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
