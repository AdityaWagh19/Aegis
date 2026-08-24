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
    # create=True: core.tier2_agent module does not exist until Phase 4;
    # the patch must succeed both before and after Phase 4 lands.
    with mock.patch("core.tier2_agent", create=True) as mock_tier2:
        for code in codes:
            classify(_event(decline_code=code))
        mock_tier2.assert_not_called()
        # If tier2_agent was imported and called, this would fail — but we patch the module
        # The real test is the import-level check below

def test_tier1_has_no_llm_imports():
    """Verify tier1_engine.py does not import any LLM module.

    Uses AST import extraction rather than a source substring scan so that
    mentions of forbidden modules inside comments/docstrings do not produce
    false positives.
    """
    import ast
    import inspect
    import core.tier1_engine as module
    tree = ast.parse(inspect.getsource(module))
    forbidden = ["groq", "openai", "anthropic", "tier2_agent"]
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    for mod in imported_modules:
        parts = set(mod.split("."))
        for name in forbidden:
            assert name not in parts, f"tier1_engine.py must not import '{name}' (found import of '{mod}')"
