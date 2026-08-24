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
    """Compliance gate must not import from Tier-1 or Tier-2 engine modules.

    Uses AST import extraction rather than a source substring scan so that
    mentions of forbidden modules inside comments/docstrings do not produce
    false positives.
    """
    import ast
    import core.compliance_gate as module
    tree = ast.parse(inspect.getsource(module))
    forbidden = ["tier1_engine", "tier2_agent", "groq", "openai"]
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    for mod in imported_modules:
        parts = set(mod.split("."))
        for name in forbidden:
            assert name not in parts, f"compliance_gate.py must not import '{name}' (found import of '{mod}')"

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
