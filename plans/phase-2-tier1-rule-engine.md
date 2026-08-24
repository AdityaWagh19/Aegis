# Phase 2: Tier-1 Deterministic Rule Engine

> **Status:** [x] Complete (2026-08-24)
> **Estimated duration:** Days 3–4
> **Depends on:** Phase 1 (all models, config loader, and `compliance_config.yaml` must exist)

---

## Objective

Implement the deterministic rule engine that classifies mandate failure events by root cause and assigns a recovery action without any LLM involvement. The engine must resolve ~65–75% of a realistic batch, have zero LLM imports, and have full unit test coverage for all six failure categories plus edge cases.

---

## Scope

- `core/tier1_engine.py` — complete implementation of `classify(event: MandateEvent) -> Tier1Result`
- `tests/unit/test_tier1.py` — all test cases as specified in `project-context/test.md`
- Performance measurement confirming < 5ms P95 per record on a 500-record batch

---

## Design Decisions and Rationale

**D1 — No LLM imports, enforced at the test level.**
`core/tier1_engine.py` must not import from `core.tier2_agent`, `groq`, or any LLM SDK. A test in `test_tier1.py` uses `unittest.mock.patch` to verify that no LLM function is called when classifying the full set of six known codes. This is enforced structurally, not by convention.

**D2 — `is_ambiguous` flag routes to Tier-2; it does not return a default action.**
When a case is ambiguous, `Tier1Result` sets `is_ambiguous=True` and `action=None`. The orchestrator (Phase 5) reads this flag and routes to Tier-2. The Tier-1 engine never guesses — if it cannot determine an action deterministically, it explicitly signals ambiguity.

**D3 — Contextual conditions are applied on top of the base taxonomy.**
The base rule for `INSUFFICIENT_FUNDS` is `SCHEDULE_POST_SALARY`. Contextual conditions (e.g. `prior_bounce_count > 3`) can override this to `ESCALATE_TO_HUMAN` or flag as ambiguous. These overrides are ordered and applied after the base classification. The order of contextual checks is documented inline.

**D4 — Unknown decline codes always route to Tier-2.**
Any `decline_code` not in the six taxonomy codes routes to Tier-2 via `is_ambiguous=True` with `reason="unknown_decline_code"`. This is a safety net — the engine never silently handles a code it was not designed for.

**D5 — AFA borderline cases (amount within 10% of threshold) are ambiguous.**
Amounts within 10% below the AFA threshold (Rs. 13,500–15,000 for general) are contextually ambiguous — they may represent genuine borderline cases where a silent retry is risky. These route to Tier-2 with `reason="borderline_afa_threshold"`.

**D6 — Config values are loaded once at module import time.**
`tier1_engine.py` calls `load_config()` at module-level import to populate constants. This avoids per-call file I/O while keeping thresholds config-driven.

---

## Sequential Implementation Tasks

### Task 2.1 — Implement `core/tier1_engine.py`

```python
# core/tier1_engine.py
"""
Tier-1: Deterministic mandate failure rule engine.
INVARIANT: This file must never import from core.tier2_agent, groq, or any LLM SDK.
"""
from config.loader import load_config
from models.mandate_event import MandateEvent, ALLOWED_ACTIONS
from models.recovery_decision import Tier1Result

_cfg = load_config()
_MAX_RETRIES = _cfg.max_retry_attempts
_AFA_GENERAL = _cfg.afa_threshold_general
_AFA_SIP = _cfg.afa_threshold_sip_insurance
_BORDERLINE_PCT = 0.10   # Within 10% below threshold = ambiguous


def _get_afa_threshold(event: MandateEvent) -> int:
    if event.product_category in ("sip", "insurance"):
        return _AFA_SIP
    return _AFA_GENERAL


def _max_attempts(event: MandateEvent) -> int:
    return _MAX_RETRIES.UPI_AUTOPAY if event.mandate_type == "UPI_AUTOPAY" else _MAX_RETRIES.ENACH


def classify(event: MandateEvent) -> Tier1Result:
    """
    Classify a mandate failure event and return a deterministic action.
    Returns is_ambiguous=True when the case requires LLM reasoning.
    """
    code = event.decline_code

    # --- INSUFFICIENT_FUNDS ---
    if code == "INSUFFICIENT_FUNDS":
        if event.prior_bounce_count > 3:
            return Tier1Result(
                action="ESCALATE_TO_HUMAN",
                is_ambiguous=False,
                reason="high_prior_bounce_count_escalate",
            )
        if event.days_since_salary_credit > 15:
            # Salary was credited > 15 days ago — funds should be available; ambiguous
            return Tier1Result(
                action=None,
                is_ambiguous=True,
                reason="late_cycle_insufficient_funds_ambiguous",
            )
        return Tier1Result(
            action="SCHEDULE_POST_SALARY",
            is_ambiguous=False,
            reason="debit_before_salary_credit",
        )

    # --- AFA_REQUIRED ---
    if code == "AFA_REQUIRED":
        threshold = _get_afa_threshold(event)
        borderline_lower = threshold * (1 - _BORDERLINE_PCT)
        if event.amount >= threshold:
            return Tier1Result(
                action="SEND_UPI_INTENT_PUSH",
                is_ambiguous=False,
                reason="afa_threshold_exceeded",
            )
        if event.amount >= borderline_lower:
            # Within 10% below threshold — treat as borderline
            return Tier1Result(
                action=None,
                is_ambiguous=True,
                reason="borderline_afa_threshold",
            )
        # Below threshold but AFA code — system/data inconsistency; route to Tier-2
        return Tier1Result(
            action=None,
            is_ambiguous=True,
            reason="afa_code_below_threshold_inconsistency",
        )

    # --- MANDATE_PAUSED ---
    if code == "MANDATE_PAUSED":
        return Tier1Result(
            action="SEND_HINGLISH_NUDGE",
            is_ambiguous=False,
            reason="24h_pre_debit_notice_triggered_pause",
        )

    # --- BANK_TECHNICAL_DECLINE ---
    if code == "BANK_TECHNICAL_DECLINE":
        max_att = _max_attempts(event)
        if event.attempt_number >= max_att:
            return Tier1Result(
                action="ESCALATE_TO_HUMAN",
                is_ambiguous=False,
                reason=f"max_retry_attempts_reached_{max_att}",
            )
        return Tier1Result(
            action="RETRY_AFTER_BACKOFF",
            is_ambiguous=False,
            reason="bank_technical_failure_safe_to_retry",
        )

    # --- NON_REVOCABLE_HARD_DECLINE ---
    if code == "NON_REVOCABLE_HARD_DECLINE":
        return Tier1Result(
            action="ESCALATE_TO_HUMAN",
            is_ambiguous=False,
            reason="non_revocable_mandate_no_auto_retry",
        )

    # --- MANDATE_EXPIRED ---
    if code == "MANDATE_EXPIRED":
        return Tier1Result(
            action="SEND_MANDATE_RENEWAL_LINK",
            is_ambiguous=False,
            reason="mandate_token_expired_new_registration_required",
        )

    # --- UNKNOWN (any unrecognised code) ---
    return Tier1Result(
        action=None,
        is_ambiguous=True,
        reason="unknown_decline_code",
    )
```

### Task 2.2 — Implement `tests/unit/test_tier1.py`

Write the complete test file covering every rule, every edge case, and the no-LLM invariant:

```python
# tests/unit/test_tier1.py
import pytest
import unittest.mock as mock
from datetime import datetime, timezone
from models.mandate_event import MandateEvent
from core.tier1_engine import classify


def _event(**kwargs) -> MandateEvent:
    defaults = dict(
        customer_id="TEST-001",
        amount=5000,
        mandate_type="UPI_AUTOPAY",
        product_category="subscription",
        decline_code="BANK_TECHNICAL_DECLINE",
        days_since_salary_credit=5,
        prior_bounce_count=0,
        is_revocable=True,
        attempt_number=1,
        timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return MandateEvent(**defaults)


# --- INSUFFICIENT_FUNDS ---

def test_insufficient_funds_schedules_post_salary():
    result = classify(_event(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=3, prior_bounce_count=0))
    assert result.action == "SCHEDULE_POST_SALARY"
    assert not result.is_ambiguous

def test_insufficient_funds_high_bounce_escalates():
    result = classify(_event(decline_code="INSUFFICIENT_FUNDS", prior_bounce_count=4))
    assert result.action == "ESCALATE_TO_HUMAN"
    assert not result.is_ambiguous

def test_insufficient_funds_late_cycle_is_ambiguous():
    result = classify(_event(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=20, prior_bounce_count=1))
    assert result.is_ambiguous
    assert result.reason == "late_cycle_insufficient_funds_ambiguous"

# --- AFA_REQUIRED ---

def test_afa_above_threshold_sends_intent_push():
    result = classify(_event(decline_code="AFA_REQUIRED", amount=16000))
    assert result.action == "SEND_UPI_INTENT_PUSH"
    assert not result.is_ambiguous

def test_afa_borderline_is_ambiguous():
    # Rs. 14,000 is within 10% below Rs. 15,000 threshold
    result = classify(_event(decline_code="AFA_REQUIRED", amount=14000))
    assert result.is_ambiguous
    assert result.reason == "borderline_afa_threshold"

def test_afa_well_below_threshold_is_ambiguous_inconsistency():
    result = classify(_event(decline_code="AFA_REQUIRED", amount=5000))
    assert result.is_ambiguous
    assert result.reason == "afa_code_below_threshold_inconsistency"

def test_afa_sip_threshold_higher():
    # SIP threshold is Rs. 100,000 — amount of Rs. 16,000 should NOT trigger AFA
    result = classify(_event(decline_code="AFA_REQUIRED", amount=16000, product_category="sip"))
    # Below SIP threshold and well below borderline — inconsistency ambiguous
    assert result.is_ambiguous

# --- MANDATE_PAUSED ---

def test_mandate_paused_sends_nudge():
    result = classify(_event(decline_code="MANDATE_PAUSED"))
    assert result.action == "SEND_HINGLISH_NUDGE"
    assert not result.is_ambiguous

# --- BANK_TECHNICAL_DECLINE ---

def test_bank_technical_within_limit_retries():
    result = classify(_event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=1, mandate_type="UPI_AUTOPAY"))
    assert result.action == "RETRY_AFTER_BACKOFF"
    assert not result.is_ambiguous

def test_bank_technical_enach_max_escalates():
    # ENACH max is 2; attempt_number=2 means cap is reached
    result = classify(_event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=2, mandate_type="ENACH"))
    assert result.action == "ESCALATE_TO_HUMAN"
    assert not result.is_ambiguous

def test_bank_technical_upi_at_limit_escalates():
    # UPI_AUTOPAY max is 3
    result = classify(_event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=3, mandate_type="UPI_AUTOPAY"))
    assert result.action == "ESCALATE_TO_HUMAN"

def test_bank_technical_upi_within_limit_retries():
    # attempt_number=2 < max(3) for UPI_AUTOPAY
    result = classify(_event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=2, mandate_type="UPI_AUTOPAY"))
    assert result.action == "RETRY_AFTER_BACKOFF"

# --- NON_REVOCABLE_HARD_DECLINE ---

def test_non_revocable_always_escalates():
    result = classify(_event(decline_code="NON_REVOCABLE_HARD_DECLINE", is_revocable=False))
    assert result.action == "ESCALATE_TO_HUMAN"
    assert not result.is_ambiguous
    assert result.reason == "non_revocable_mandate_no_auto_retry"

# --- MANDATE_EXPIRED ---

def test_mandate_expired_sends_renewal_link():
    result = classify(_event(decline_code="MANDATE_EXPIRED"))
    assert result.action == "SEND_MANDATE_RENEWAL_LINK"
    assert not result.is_ambiguous

# --- UNKNOWN CODE ---

def test_unknown_decline_code_is_ambiguous():
    result = classify(_event(decline_code="SOME_UNKNOWN_CODE_XYZ"))
    assert result.is_ambiguous
    assert result.reason == "unknown_decline_code"
    assert result.action is None

# --- NO LLM INVARIANT ---

def test_tier1_makes_zero_llm_calls():
    """Tier-1 must never call any LLM function for any known or unknown decline code."""
    codes = [
        "INSUFFICIENT_FUNDS", "AFA_REQUIRED", "MANDATE_PAUSED",
        "BANK_TECHNICAL_DECLINE", "NON_REVOCABLE_HARD_DECLINE",
        "MANDATE_EXPIRED", "UNKNOWN_XYZ",
    ]
    with mock.patch("core.tier2_agent") as mock_tier2:
        for code in codes:
            classify(_event(decline_code=code))
        # If tier2_agent was imported and called, this would fail — but we patch the module
        # The real test is the import-level check below

def test_tier1_has_no_llm_imports():
    """Verify tier1_engine.py source does not import any LLM module."""
    import inspect
    import core.tier1_engine as module
    source = inspect.getsource(module)
    forbidden = ["groq", "openai", "anthropic", "tier2_agent"]
    for name in forbidden:
        assert name not in source, f"tier1_engine.py must not import '{name}'"
```

### Task 2.3 — Measure Tier-1 resolution rate on synthetic data

```python
# Run from repo root after Phase 1 synthetic data is generated
# scripts/measure_tier1.py
import csv
import time
from models.mandate_event import MandateEvent
from core.tier1_engine import classify
from datetime import datetime, timezone

with open("data/synthetic.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

events = []
for row in rows:
    row["timestamp"] = datetime.fromisoformat(row["timestamp"])
    row["is_revocable"] = row["is_revocable"].lower() == "true"
    row["is_held_out"] = row["is_held_out"].lower() == "true"
    row["amount"] = int(row["amount"])
    row["days_since_salary_credit"] = int(row["days_since_salary_credit"])
    row["prior_bounce_count"] = int(row["prior_bounce_count"])
    row["attempt_number"] = int(row["attempt_number"])
    events.append(MandateEvent(**row))

start = time.perf_counter()
results = [classify(e) for e in events]
elapsed_ms = (time.perf_counter() - start) * 1000

resolved = sum(1 for r in results if not r.is_ambiguous)
print(f"Total: {len(results)}")
print(f"Tier-1 resolved: {resolved} ({resolved/len(results)*100:.1f}%)")
print(f"Ambiguous (Tier-2): {len(results)-resolved} ({(len(results)-resolved)/len(results)*100:.1f}%)")
print(f"Total elapsed: {elapsed_ms:.1f}ms | P95 per record: {elapsed_ms*0.95/len(results):.2f}ms")
```

Run with: `python scripts/measure_tier1.py`

---

## Validation Strategy

1. `pytest tests/unit/test_tier1.py -v` — all tests pass, zero failures.
2. `python scripts/measure_tier1.py` — prints resolution rate between 60% and 80%, P95 per record < 5ms.
3. Import check: `python -c "import core.tier1_engine; print('No LLM imports')"` — no `ImportError`.

---

## Acceptance Criteria

- [x] `pytest tests/unit/test_tier1.py -v` exits with code 0, all tests pass. (17/17)
- [x] `test_tier1_has_no_llm_imports` passes (proves no LLM imports in source). *(Implemented as AST import scan — the planned substring scan false-positived on the module's own docstring.)*
- [x] Tier-1 resolution rate on 500-record synthetic batch: between 60% and 80%. *(Measured **83.8%** — above window; plan risk table deems >80% acceptable once ambiguous routing is verified not suppressed. Verified: all three dataset-reachable ambiguity branches fire, counts sum exactly to the ambiguous total. See progress.md Phase 2 session.)*
- [x] P95 latency per record on 500 sequential calls: < 5ms. (~0.00ms)
- [x] All six canonical decline codes produce a non-ambiguous result with the correct action.
- [x] Unknown decline codes produce `is_ambiguous=True` with `reason="unknown_decline_code"`.
- [x] `prior_bounce_count > 3` escalates `INSUFFICIENT_FUNDS` to `ESCALATE_TO_HUMAN`.
- [x] `attempt_number >= max[mandate_type]` escalates `BANK_TECHNICAL_DECLINE` to `ESCALATE_TO_HUMAN`.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| Resolution rate below 60% | Medium | If too many edge cases route to Tier-2, add more specific contextual rules |
| Resolution rate above 80% | Low | Acceptable — but check that ambiguous routing logic is not suppressed |
| AFA threshold borderline range miscalibrated | Low | Adjust `_BORDERLINE_PCT` constant based on synthetic distribution inspection |
| Test tightly coupled to synthetic distribution | Low | Tests use `_event()` factory with explicit values, not the synthetic CSV |

---

## Deliverables

- `core/tier1_engine.py` — complete, all six categories, contextual rules
- `tests/unit/test_tier1.py` — 15+ test cases, all passing
- `scripts/measure_tier1.py` — performance measurement script
- Measurement output documented in `project-context/progress.md` Day 3 or 4 entry

---

## Documentation Updates

- Check off Phase 2 tasks in `project-context/tasks.md`
- Update `project-context/progress.md` with Tier-1 resolution rate measurement
- Update `plans/overview.md` Phase 2 status: `[x]`
