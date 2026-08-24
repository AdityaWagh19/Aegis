# Phase 8: Evaluation and Submission

> **Status:** [ ] Not started
> **Estimated duration:** Days 12–13
> **Depends on:** Phase 7 (full working system deployed and accessible at the demo URL)

---

## Objective

Run the held-out evaluation to produce honest metrics, verify that zero compliance violations reach execution, prepare all submission artifacts, rehearse the demo, and record the final 5-minute video. Nothing is modified after the demo is recorded without a documented reason.

---

## Scope

- Complete `synthetic/evaluator.py` (the skeleton was created in Phase 1)
- Deploy the full system to EC2 using the procedure in `project-context/deploy.md`
- Run the held-out evaluation and assert `compliance_violations_executed == 0`
- Record the demo video following `project-context/demo.md`
- Copy `project-context/progress.md` to `BUILD_LOG.md` in repo root
- Final git commit and push

---

## Design Decisions and Rationale

**D1 — Held-out evaluation runs against the live pipeline, not a stub.**
`evaluate_held_out_set()` calls `process_batch()` with the 100 held-out events. This is the same code path the demo runs. It is not a separate evaluation harness. If the evaluation fails, the demo would also fail — catching it here is the point.

**D2 — `compliance_violations_executed == 0` is a hard assertion, not a metric to report.**
The evaluation script calls `assert result.compliance_violations_executed == 0` and raises with a clear error message if it fails. Do not continue to demo recording if this assertion fails.

**D3 — Metrics are reported honestly, including anything unflattering.**
If Tier-1 resolution rate is 58% (below the 65% target), it is reported as 58%, not suppressed. The judges are evaluating the engineering approach, not asking for a certain number.

**D4 — `BUILD_LOG.md` is a verbatim copy of `project-context/progress.md`.**
No sanitising, no retroactive editing of failure entries. The log must show genuine real failures encountered during the build.

---

## Sequential Implementation Tasks

### Task 8.1 — Complete `synthetic/evaluator.py`

```python
# synthetic/evaluator.py
"""
Held-out evaluation.
Runs the full pipeline on the held-out set and reports metrics.
CRITICAL: Call this before recording the demo. Assert compliance_violations_executed == 0.
"""
import asyncio
import csv
import json
from datetime import datetime, timezone

from models.mandate_event import MandateEvent
from models.recovery_decision import EvaluationResult
from core.orchestrator import process_batch


def load_held_out_events(path: str = "data/synthetic_held_out.csv") -> list[MandateEvent]:
    events = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
            row["is_revocable"] = row["is_revocable"].lower() == "true"
            row["is_held_out"] = row["is_held_out"].lower() == "true"
            row["amount"] = int(row["amount"])
            row["days_since_salary_credit"] = int(row["days_since_salary_credit"])
            row["prior_bounce_count"] = int(row["prior_bounce_count"])
            row["attempt_number"] = int(row["attempt_number"])
            events.append(MandateEvent(**row))
    return events


async def _run_evaluation(events: list[MandateEvent]) -> EvaluationResult:
    batch_result = await process_batch(events)

    correct = sum(
        1
        for decision, event in zip(batch_result.decisions, events)
        if event.correct_action and decision.final_action == event.correct_action
    )

    # Per-category accuracy
    from collections import defaultdict
    cat_correct: dict[str, list[bool]] = defaultdict(list)
    for decision, event in zip(batch_result.decisions, events):
        if event.correct_action:
            cat_correct[event.decline_code].append(decision.final_action == event.correct_action)

    recovery_by_category = {
        cat: round(sum(vals) / len(vals), 4)
        for cat, vals in cat_correct.items()
    }

    # False escalation: escalated but correct_action was not ESCALATE_TO_HUMAN
    false_escalations = sum(
        1
        for decision, event in zip(batch_result.decisions, events)
        if decision.final_action == "ESCALATE_TO_HUMAN"
        and event.correct_action != "ESCALATE_TO_HUMAN"
    )
    false_escalation_rate = false_escalations / len(events) if events else 0.0

    return EvaluationResult(
        total_held_out=len(events),
        correct_actions=correct,
        accuracy=round(correct / len(events), 4) if events else 0.0,
        recovery_rate_by_category=recovery_by_category,
        false_escalation_rate=round(false_escalation_rate, 4),
        tier1_resolution_rate=round(batch_result.metrics.tier1_pct / 100, 4),
        tier2_resolution_rate=round(batch_result.metrics.tier2_count / len(events), 4) if events else 0.0,
        compliance_violations_caught=batch_result.metrics.compliance_violations_caught,
        compliance_violations_executed=batch_result.metrics.compliance_violations_executed,
    )


def evaluate_held_out_set(path: str = "data/synthetic_held_out.csv") -> EvaluationResult:
    """
    Load the held-out set and run the full pipeline evaluation.

    IMPORTANT: Do NOT call this function from inside an async context (e.g., an
    asyncio test, a pytest-asyncio test, or a Jupyter notebook with an active
    event loop). `asyncio.run()` will raise `RuntimeError: This event loop is
    already running` in those environments.

    Correct usage: `python -m synthetic.evaluator` from the terminal.
    """
    events = load_held_out_events(path)
    result = asyncio.run(_run_evaluation(events))

    # Print report
    print("\n" + "=" * 60)
    print("AEGIS HELD-OUT EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total held-out records:     {result.total_held_out}")
    print(f"Correct actions:            {result.correct_actions}")
    print(f"Overall accuracy:           {result.accuracy:.1%}")
    print(f"Tier-1 resolution rate:     {result.tier1_resolution_rate:.1%}")
    print(f"Tier-2 resolution rate:     {result.tier2_resolution_rate:.1%}")
    print(f"False escalation rate:      {result.false_escalation_rate:.1%}")
    print(f"Compliance violations caught:   {result.compliance_violations_caught}")
    print(f"Compliance violations executed: {result.compliance_violations_executed}")
    print("\nRecovery rate by category:")
    for cat, rate in sorted(result.recovery_rate_by_category.items()):
        print(f"  {cat:<35} {rate:.1%}")
    print("=" * 60)

    # HARD ASSERTION — do not record demo if this fails
    assert result.compliance_violations_executed == 0, (
        f"\nCRITICAL: {result.compliance_violations_executed} compliance violation(s) reached execution.\n"
        "Do not record the demo until this is resolved.\n"
        "Check compliance_gate.py and action_executor.py."
    )
    print("\nAssertion passed: compliance_violations_executed == 0")
    print("Safe to proceed to demo recording.\n")

    # Write results to file for submission reference
    with open("evaluation_results.json", "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    print("Results written to evaluation_results.json")

    return result


if __name__ == "__main__":
    evaluate_held_out_set()
```

### Task 8.2 — Run full pre-demo test suite

Execute in this exact order. All must pass before moving to Task 8.3.

```bash
# Step 1: Unit tests
pytest tests/unit/ -v --tb=short
echo "--- Unit tests complete ---"

# Step 2: Compliance gate (run separately for visibility)
pytest tests/unit/test_compliance_gate.py -v --tb=long
echo "--- Compliance gate tests complete ---"

# Step 3: Integration tests
pytest tests/integration/ -v --tb=short
echo "--- Integration tests complete ---"

# Step 4: Held-out evaluation
python -m synthetic.evaluator
echo "--- Evaluation complete ---"
```

Record the output of Step 4 in `project-context/progress.md` Day 12 entry (verbatim).

### Task 8.3 — Deploy to EC2

Follow `project-context/deploy.md` exactly. Checklist:

```bash
# On EC2 — verify .env is present and correct
ls -la /home/ubuntu/Aegis/.env
cat /home/ubuntu/Aegis/.env | grep GROQ_API_KEY   # Should show key prefix only

# Pull latest main branch
cd /home/ubuntu/Aegis
git pull origin main

# Build React dashboard
cd dashboard && npm ci && npm run build && cd ..

# Start services
docker compose up --build -d

# Verify
curl http://localhost:8000/health
curl -I https://aegis.yourdomain.com/health   # Should return 200 via Nginx + SSL
```

### Task 8.4 — Demo batch preparation

Create `data/demo_batch.csv` — 53 records specifically crafted for the demo:

```python
# scripts/make_demo_batch.py
"""Create a demo-specific batch with at least one of each category plus deliberate violations."""
import csv, uuid
from datetime import datetime, timezone

RECORDS = [
    # Category mix (rounds to ~70% Tier-1 resolvable)
    *[{"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 3, "prior_bounce_count": 0, "amount": 12000, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(18)],
    *[{"decline_code": "BANK_TECHNICAL_DECLINE", "days_since_salary_credit": 10, "prior_bounce_count": 0, "amount": 8500, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(10)],
    *[{"decline_code": "MANDATE_PAUSED", "days_since_salary_credit": 7, "prior_bounce_count": 0, "amount": 5000, "is_revocable": True, "attempt_number": 1, "mandate_type": "ENACH"} for _ in range(7)],
    *[{"decline_code": "AFA_REQUIRED", "days_since_salary_credit": 5, "prior_bounce_count": 0, "amount": 18000, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(5)],
    *[{"decline_code": "MANDATE_EXPIRED", "days_since_salary_credit": 12, "prior_bounce_count": 0, "amount": 7500, "is_revocable": True, "attempt_number": 1, "mandate_type": "ENACH"} for _ in range(5)],
    # Deliberately ambiguous -> Tier-2
    *[{"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 22, "prior_bounce_count": 2, "amount": 9000, "is_revocable": True, "attempt_number": 2, "mandate_type": "UPI_AUTOPAY"} for _ in range(5)],
    *[{"decline_code": "AFA_REQUIRED", "days_since_salary_credit": 5, "prior_bounce_count": 0, "amount": 14200, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(2)],
    # THE COMPLIANCE OVERRIDE MOMENT — mandate MAND-042
    {"decline_code": "NON_REVOCABLE_HARD_DECLINE", "days_since_salary_credit": 1, "prior_bounce_count": 2, "amount": 45000, "is_revocable": False, "attempt_number": 2, "mandate_type": "ENACH"},
]

now = datetime.now(timezone.utc).isoformat()
fieldnames = ["mandate_id","customer_id","amount","mandate_type","product_category",
              "decline_code","days_since_salary_credit","prior_bounce_count",
              "is_revocable","attempt_number","timestamp","batch_id","is_held_out","correct_action"]

batch_id = str(uuid.uuid4())
rows = []
for i, r in enumerate(RECORDS):
    rows.append({
        "mandate_id": f"MAND-{i+1:03d}",
        "customer_id": f"CUST-{1000+i}",
        "product_category": "loan_emi" if not r["is_revocable"] else "subscription",
        "timestamp": now,
        "batch_id": batch_id,
        "is_held_out": False,
        "correct_action": "",
        **r,
    })

with open("data/demo_batch.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f"Demo batch created: {len(rows)} records -> data/demo_batch.csv")
print("NON_REVOCABLE mandate ID: MAND-053 (the 53rd record — the compliance override case)")
```

Run: `python scripts/make_demo_batch.py`

### Task 8.5 — Pre-demo verification checklist

Run through every item in `project-context/demo.md` Pre-Demo Checklist. All items must be checked before recording.

Critical items that must be verified by command, not by assumption:

```bash
# Verify compliance assertion
python -m synthetic.evaluator 2>&1 | grep "compliance_violations_executed"
# Expected: "Compliance violations executed: 0" and "Assertion passed"

# Verify unit tests
pytest tests/unit/ -q 2>&1 | tail -3
# Expected: "X passed in Xs"

# Verify API is responding at demo URL
curl -s https://aegis.yourdomain.com/health | python -m json.tool
# Expected: {"status": "ok"}

# Verify demo batch uploads successfully
curl -X POST https://aegis.yourdomain.com/api/v1/recovery/batch \
  -F "file=@data/demo_batch.csv" | python -m json.tool | grep compliance_violations_caught
# Expected: "compliance_violations_caught": N (where N > 0)
```

### Task 8.6 — Record the 5-minute demo video

Follow `project-context/demo.md` script exactly. The compliance override moment (the non-revocable mandate) must be clearly visible on screen. Record at 1920x1080.

Checklist before pressing record:
- [ ] Browser: Dashboard tab loaded at demo URL
- [ ] Browser: Batch upload tab ready
- [ ] Terminal: Backend logs visible (for narrating real-time decisions)
- [ ] `data/demo_batch.csv` is ready on local machine for upload
- [ ] Microphone tested — audio is clear
- [ ] Screen recording software is running

### Task 8.7 — Prepare submission artifacts

```bash
# Copy progress log to BUILD_LOG.md
cp project-context/progress.md BUILD_LOG.md

# Stage and commit everything
git add -A
git commit -m "feat: complete Aegis MVP — all phases implemented, evaluation passed, demo ready"
git push origin main

# Verify final state
git log --oneline -5
git status
```

### Task 8.8 — Final submission

Submit via the hackathon portal with the following:

| Artifact | Source |
|---|---|
| GitHub repository URL | `https://github.com/AdityaWagh19/Aegis` |
| Architecture diagram | README.md Mermaid diagrams |
| 5-minute demo video | Recorded in Task 8.6 |
| `BUILD_LOG.md` | Copied from `project-context/progress.md` |
| Held-out evaluation metrics | `evaluation_results.json` in repo root |

---

## Validation Strategy

All of the following must be true before submission:

1. `pytest tests/unit/ -q` — all pass.
2. `python -m synthetic.evaluator` — prints results and exits without assertion error.
3. `evaluation_results.json` in repo root with non-zero `total_held_out`.
4. `BUILD_LOG.md` in repo root with at least 8 day entries.
5. Demo video plays correctly from start to finish with the compliance override moment visible.

---

## Acceptance Criteria

- [ ] `pytest tests/unit/ -v` exits with code 0.
- [ ] `python -m synthetic.evaluator` exits with code 0 and prints "Assertion passed: compliance_violations_executed == 0".
- [ ] `evaluation_results.json` exists in repo root with `compliance_violations_executed: 0`.
- [ ] `BUILD_LOG.md` exists in repo root (copied from `project-context/progress.md`).
- [ ] All submission artifacts listed in Task 8.8 are prepared.
- [ ] `git status` shows clean working tree on `main`.
- [ ] Demo video is 4–6 minutes long and includes the compliance override card visible on screen.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| `compliance_violations_executed > 0` assertion fails | Low | Fix compliance gate before recording. Never skip this check. |
| EC2 instance too slow for 52-record batch in demo | Medium | Use t3.medium; if slow, run demo locally and deploy separately |
| Demo video quality poor | Medium | Rehearse 3 times before recording; use OBS for reliable capture |
| `BUILD_LOG.md` has fewer than 8 day entries | Medium | Write progress.md entries daily; do not wait until Day 12 |
| Groq rate limit hit during demo | Low | Switch to `llama-3.1-8b-instant` if `llama-3.3-70b-versatile` is rate-limited |

---

## Deliverables

- `synthetic/evaluator.py` — complete, callable, assertion on zero violations
- `evaluation_results.json` — written by evaluator
- `BUILD_LOG.md` — in repo root
- `data/demo_batch.csv` — 52 records for demo (committed)
- `scripts/make_demo_batch.py`
- Final commit on `main` branch

---

## Documentation Updates

- Mark all tasks in `project-context/tasks.md` as `[x]`
- Write Day 12 and Day 13 entries in `project-context/progress.md` / `BUILD_LOG.md`
- Update `plans/overview.md` Phase 8 status: `[x]`
- Update all phase statuses in `plans/overview.md` to `[x]`
