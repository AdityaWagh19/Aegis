# Phase 3: Compliance Gate

> **Status:** [ ] Not started
> **Estimated duration:** Day 5
> **Depends on:** Phase 1 (models, config loader)
> **Note:** Phase 3 is independent of Phase 2. It can be built while Phase 2 tests are being run. However, sequencing Phase 3 after Phase 2 reduces context-switching.

---

## Objective

Implement the unconditional compliance gate as an isolated, pure-function module. The gate must enforce all four compliance rules, have unit tests for every rule's activation and pass-through cases, and have zero dependency on Tier-1 or Tier-2 code. This phase ends with a fully tested compliance gate that is ready to be wired into the orchestrator in Phase 5.

---

## Scope

- `core/compliance_gate.py` — `ComplianceGate.check(event, proposed_action) -> ComplianceResult`
- `tests/unit/test_compliance_gate.py` — full rule coverage: 2 tests per rule (activation + pass-through), plus general pass-through and structural isolation tests
- Structural verification: no imports from `core.tier1_engine` or `core.tier2_agent`

---

## Design Decisions and Rationale

**D1 — The gate is a class, not a module-level function.**
`ComplianceGate` is instantiated once at application startup with a `ComplianceConfig`. This makes it testable without relying on the filesystem (the config is injected, not loaded inside the function). It also makes the gate's dependencies explicit.

**D2 — All four rules run in sequence, and the first violation terminates the check.**
Rules are ordered by severity: non-revocable > max-retry > AFA > 24h notice. The first triggered rule determines the outcome. This ordering means the most legally severe constraint is checked first.

**D3 — `violation_blocked=True` is set on any rejected action.**
The `ComplianceResult` always carries `violation_blocked` and `violation_rule`. This is the data that populates the audit log's "violations caught" count. The dashboard reads this field directly.

**D4 — The gate has no access to the database.**
The gate is a pure function of `(MandateEvent, proposed_action) -> ComplianceResult`. It never queries the database, calls an external service, or reads from the filesystem (all config is injected at construction time). This keeps it synchronous, testable, and infinitely parallelisable.

**D5 — Rejected actions are redirected, not left as `None`.**
When a violation is caught, the gate sets `final_action` to the only legally permissible alternative:
- Non-revocable violation → `ESCALATE_TO_HUMAN`
- Max-retry violation → `ESCALATE_TO_HUMAN`
- AFA violation → `SEND_UPI_INTENT_PUSH`
- 24h notice violation → `SEND_HINGLISH_NUDGE`

The executor never receives `None` as `final_action`.

---

## Sequential Implementation Tasks

### Task 3.1 — Implement `core/compliance_gate.py`

```python
# core/compliance_gate.py
"""
Compliance Gate — unconditional NPCI/RBI rule enforcement.

INVARIANTS:
1. Pure function: same inputs always produce the same output.
2. No imports from core.tier1_engine or core.tier2_agent.
3. Cannot be configured off — no feature flag, env var, or API param disables it.
4. Its output (final_action) is the ONLY input to the action executor.
"""
from models.mandate_event import MandateEvent, RETRY_ACTIONS
from models.recovery_decision import ComplianceResult
from config.loader import ComplianceConfig, load_config


class ComplianceGate:

    def __init__(self, config: ComplianceConfig | None = None):
        self._cfg = config or load_config()

    def check(self, event: MandateEvent, proposed_action: str) -> ComplianceResult:
        """
        Enforce all four compliance rules in order.
        Returns a ComplianceResult with the final_action that may execute.
        """
        # Rule 1: Non-revocable mandate — only ESCALATE_TO_HUMAN is permitted
        if not event.is_revocable and event.decline_code == "NON_REVOCABLE_HARD_DECLINE":
            if proposed_action != "ESCALATE_TO_HUMAN":
                return ComplianceResult(
                    approved=False,
                    final_action="ESCALATE_TO_HUMAN",
                    violation_blocked=True,
                    violation_rule="non_revocable_mandate_no_auto_retry",
                )

        # Rule 2: Max retry attempts — cap retries per mandate type
        max_attempts = self._get_max_attempts(event)
        if event.attempt_number >= max_attempts and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="ESCALATE_TO_HUMAN",
                violation_blocked=True,
                violation_rule=f"max_retry_attempts_exceeded_{max_attempts}",
            )

        # Rule 3: AFA threshold — silent retry above threshold violates NPCI rules
        threshold = self._get_afa_threshold(event)
        if event.amount > threshold and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="SEND_UPI_INTENT_PUSH",
                violation_blocked=True,
                violation_rule=f"afa_threshold_requires_intent_push_{threshold}",
            )

        # Rule 4: 24h pre-debit notice — retrying on a paused mandate violates RBI rules
        if event.decline_code == "MANDATE_PAUSED" and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="SEND_HINGLISH_NUDGE",
                violation_blocked=True,
                violation_rule="24h_pre_debit_notice_no_retry",
            )

        # All rules passed
        return ComplianceResult(
            approved=True,
            final_action=proposed_action,
            violation_blocked=False,
            violation_rule=None,
        )

    def _get_max_attempts(self, event: MandateEvent) -> int:
        if event.mandate_type == "UPI_AUTOPAY":
            return self._cfg.max_retry_attempts.UPI_AUTOPAY
        return self._cfg.max_retry_attempts.ENACH

    def _get_afa_threshold(self, event: MandateEvent) -> int:
        if event.product_category in ("sip", "insurance"):
            return self._cfg.afa_threshold_sip_insurance
        return self._cfg.afa_threshold_general
```

### Task 3.2 — Implement `tests/unit/test_compliance_gate.py`

```python
# tests/unit/test_compliance_gate.py
"""
CRITICAL: These tests prove the compliance gate cannot be bypassed.
Every rule has:
  - An activation test: the violation IS caught
  - A pass-through test: a compliant action IS approved
All tests must pass before Phase 5 begins.
"""
import pytest
import inspect
from datetime import datetime, timezone
from models.mandate_event import MandateEvent
from models.recovery_decision import ComplianceResult
from core.compliance_gate import ComplianceGate

gate = ComplianceGate()


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


# =============================================================================
# RULE 1: Non-Revocable Mandate Hard Decline
# =============================================================================

def test_rule1_non_revocable_retry_blocked():
    event = _event(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.final_action == "ESCALATE_TO_HUMAN"
    assert result.violation_blocked is True
    assert result.violation_rule == "non_revocable_mandate_no_auto_retry"

def test_rule1_non_revocable_schedule_blocked():
    event = _event(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = gate.check(event, "SCHEDULE_POST_SALARY")
    assert not result.approved
    assert result.violation_blocked is True

def test_rule1_non_revocable_nudge_blocked():
    event = _event(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = gate.check(event, "SEND_HINGLISH_NUDGE")
    assert not result.approved
    assert result.final_action == "ESCALATE_TO_HUMAN"

def test_rule1_non_revocable_escalate_passes():
    """ESCALATE_TO_HUMAN is the only permissible action for non-revocable hard declines."""
    event = _event(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = gate.check(event, "ESCALATE_TO_HUMAN")
    assert result.approved
    assert result.violation_blocked is False
    assert result.final_action == "ESCALATE_TO_HUMAN"

def test_rule1_revocable_not_triggered():
    """Rule 1 must NOT trigger when is_revocable=True, even with NON_REVOCABLE code."""
    event = _event(is_revocable=True, decline_code="NON_REVOCABLE_HARD_DECLINE", amount=5000)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    # Rule 1 does not apply; rule 2 applies (attempt_number=1 < max=3 for UPI_AUTOPAY)
    assert result.approved


# =============================================================================
# RULE 2: Max Retry Attempts Cap
# =============================================================================

def test_rule2_enach_at_max_retry_blocked():
    """ENACH max is 2. attempt_number=2 must block any retry."""
    event = _event(mandate_type="ENACH", attempt_number=2, amount=5000, is_revocable=True)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.violation_blocked is True
    assert "max_retry_attempts_exceeded_2" in result.violation_rule

def test_rule2_upi_at_max_retry_blocked():
    """UPI_AUTOPAY max is 3. attempt_number=3 must block any retry."""
    event = _event(mandate_type="UPI_AUTOPAY", attempt_number=3, amount=5000, is_revocable=True)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert not result.approved

def test_rule2_upi_below_max_passes():
    """UPI_AUTOPAY max is 3. attempt_number=2 must pass."""
    event = _event(mandate_type="UPI_AUTOPAY", attempt_number=2, amount=5000, is_revocable=True)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert result.approved

def test_rule2_enach_below_max_passes():
    """ENACH max is 2. attempt_number=1 must pass."""
    event = _event(mandate_type="ENACH", attempt_number=1, amount=5000, is_revocable=True)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert result.approved

def test_rule2_non_retry_action_not_blocked():
    """Max-retry rule only applies to RETRY_ACTIONS. ESCALATE_TO_HUMAN must pass."""
    event = _event(mandate_type="ENACH", attempt_number=5, amount=5000, is_revocable=True)
    result = gate.check(event, "ESCALATE_TO_HUMAN")
    assert result.approved


# =============================================================================
# RULE 3: AFA Threshold Routing
# =============================================================================

def test_rule3_above_general_threshold_retry_blocked():
    event = _event(amount=16000, product_category="subscription", is_revocable=True, attempt_number=1)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.final_action == "SEND_UPI_INTENT_PUSH"
    assert "afa_threshold_requires_intent_push_15000" in result.violation_rule

def test_rule3_above_general_threshold_schedule_blocked():
    event = _event(amount=20000, product_category="subscription", is_revocable=True, attempt_number=1)
    result = gate.check(event, "SCHEDULE_POST_SALARY")
    assert not result.approved
    assert result.final_action == "SEND_UPI_INTENT_PUSH"

def test_rule3_intent_push_passes_above_threshold():
    event = _event(amount=16000, product_category="subscription", is_revocable=True, attempt_number=1)
    result = gate.check(event, "SEND_UPI_INTENT_PUSH")
    assert result.approved

def test_rule3_below_threshold_retry_passes():
    event = _event(amount=10000, product_category="subscription", is_revocable=True, attempt_number=1)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert result.approved

def test_rule3_sip_threshold_higher():
    """SIP threshold is Rs. 100,000. Rs. 50,000 should pass for SIP."""
    event = _event(amount=50000, product_category="sip", is_revocable=True, attempt_number=1)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert result.approved

def test_rule3_above_sip_threshold_blocked():
    """Rs. 110,000 exceeds SIP threshold of Rs. 100,000."""
    event = _event(amount=110000, product_category="sip", is_revocable=True, attempt_number=1)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert "100000" in result.violation_rule


# =============================================================================
# RULE 4: 24h Pre-Debit Notice Active
# =============================================================================

def test_rule4_paused_mandate_retry_blocked():
    event = _event(decline_code="MANDATE_PAUSED", is_revocable=True, amount=5000, attempt_number=1)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.violation_rule == "24h_pre_debit_notice_no_retry"
    assert result.final_action == "SEND_HINGLISH_NUDGE"

def test_rule4_paused_mandate_nudge_passes():
    event = _event(decline_code="MANDATE_PAUSED", is_revocable=True, amount=5000, attempt_number=1)
    result = gate.check(event, "SEND_HINGLISH_NUDGE")
    assert result.approved

def test_rule4_paused_mandate_escalate_passes():
    event = _event(decline_code="MANDATE_PAUSED", is_revocable=True, amount=5000, attempt_number=1)
    result = gate.check(event, "ESCALATE_TO_HUMAN")
    assert result.approved

def test_rule4_non_paused_code_retry_passes():
    """Rule 4 must NOT trigger for non-MANDATE_PAUSED decline codes."""
    event = _event(decline_code="BANK_TECHNICAL_DECLINE", amount=5000, is_revocable=True, attempt_number=1)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert result.approved


# =============================================================================
# GENERAL PASS-THROUGH AND STRUCTURAL TESTS
# =============================================================================

def test_compliant_action_approved_no_violation():
    event = _event(mandate_type="UPI_AUTOPAY", attempt_number=1, is_revocable=True, amount=5000)
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert result.approved
    assert result.final_action == "RETRY_AFTER_BACKOFF"
    assert result.violation_blocked is False
    assert result.violation_rule is None

def test_compliance_gate_has_no_tier_imports():
    """Compliance gate must not import from Tier-1 or Tier-2 engine modules."""
    import core.compliance_gate as module
    source = inspect.getsource(module)
    forbidden = ["tier1_engine", "tier2_agent", "groq", "openai"]
    for name in forbidden:
        assert name not in source, f"compliance_gate.py must not import '{name}'"

def test_compliance_result_is_pydantic():
    """ComplianceResult must always be a valid Pydantic model instance."""
    event = _event()
    result = gate.check(event, "RETRY_AFTER_BACKOFF")
    assert isinstance(result, ComplianceResult)
    assert hasattr(result, "approved")
    assert hasattr(result, "final_action")
    assert hasattr(result, "violation_blocked")

def test_no_final_action_is_none():
    """gate.check() must never return final_action=None."""
    from models.mandate_event import ALLOWED_ACTIONS
    codes = [
        "INSUFFICIENT_FUNDS", "AFA_REQUIRED", "MANDATE_PAUSED",
        "BANK_TECHNICAL_DECLINE", "NON_REVOCABLE_HARD_DECLINE", "MANDATE_EXPIRED",
    ]
    for code in codes:
        event = _event(decline_code=code, is_revocable=(code != "NON_REVOCABLE_HARD_DECLINE"))
        for action in ALLOWED_ACTIONS:
            result = gate.check(event, action)
            assert result.final_action is not None, \
                f"final_action is None for decline_code={code}, proposed={action}"
```

---

## Validation Strategy

1. `pytest tests/unit/test_compliance_gate.py -v` — all tests pass, zero failures.
2. `test_compliance_gate_has_no_tier_imports` verifies structural isolation in source.
3. `test_no_final_action_is_none` verifies gate always produces a valid final action for any input combination.

---

## Acceptance Criteria

- [ ] `pytest tests/unit/test_compliance_gate.py -v` exits with code 0.
- [ ] Every rule has at least one activation test (violation caught) and one pass-through test (compliant action approved).
- [ ] `test_compliance_gate_has_no_tier_imports` passes.
- [ ] `test_no_final_action_is_none` passes — `final_action` is never `None`.
- [ ] `ComplianceResult.violation_rule` is `None` for approved actions and a non-empty string for blocked actions.
- [ ] Rule 1 (non-revocable) triggers only when `is_revocable=False` AND `decline_code="NON_REVOCABLE_HARD_DECLINE"`. It does not trigger for revocable mandates with the same code.
- [ ] Rule 3 (AFA) uses `product_category` to select between `afa_threshold_general` and `afa_threshold_sip_insurance`.
- [ ] Rule 4 (24h notice) redirects to `SEND_HINGLISH_NUDGE`, not `ESCALATE_TO_HUMAN`.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| Rule ordering bug (wrong rule triggers first) | Low | Tests verify each rule in isolation with conditions that prevent other rules triggering |
| `RETRY_ACTIONS` list not imported correctly | Low | Defined in `models/mandate_event.py`; imported explicitly, not redefined |
| AFA threshold lookup uses wrong product category | Low | Explicit test `test_rule3_sip_threshold_higher` and `test_rule3_above_sip_threshold_blocked` |
| Gate accidentally imports Tier-1 or Tier-2 | Low | Structural source inspection test catches this at the unit-test level |

---

## Deliverables

- `core/compliance_gate.py` — `ComplianceGate` class, all 4 rules, pure function
- `tests/unit/test_compliance_gate.py` — 25+ test cases, all passing

---

## Documentation Updates

- Check off Phase 3 tasks in `project-context/tasks.md`
- Update `project-context/progress.md` with compliance gate test result count
- Update `plans/overview.md` Phase 3 status: `[x]`
