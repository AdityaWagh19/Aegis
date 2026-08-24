# tests/integration/test_batch_pipeline.py
"""
Integration tests for the full batch pipeline.
These tests use mocks for Razorpay and Groq to avoid external API calls.
The DB uses SQLite (in-memory or file-based) for speed.
"""
import pytest
import asyncio
import unittest.mock as mock
from datetime import datetime, timezone

from models.mandate_event import MandateEvent
from models.recovery_decision import Tier2Result
from core.orchestrator import process_batch


def _event(**kwargs) -> MandateEvent:
    defaults = dict(
        customer_id="TEST-001", amount=5000, mandate_type="UPI_AUTOPAY",
        product_category="subscription", decline_code="BANK_TECHNICAL_DECLINE",
        days_since_salary_credit=5, prior_bounce_count=0, is_revocable=True,
        attempt_number=1, timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return MandateEvent(**defaults)


def _mock_razorpay():
    """Patch all Razorpay functions to return a mock response."""
    mock_resp = {"id": "sub_test_123", "status": "active"}
    patches = [
        mock.patch("core.action_executor.resume_subscription", return_value=mock_resp),
        mock.patch("core.action_executor.pause_subscription", return_value=mock_resp),
        mock.patch("core.action_executor.create_payment_link", return_value={"short_url": "https://rzp.io/test"}),
    ]
    return patches


@pytest.mark.asyncio
async def test_batch_tier1_resolution_rate():
    """Full pipeline: Tier-1 must resolve 60-80% of a representative batch."""
    events = [
        _event(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=3),
        _event(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=3),
        _event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=1),
        _event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=1),
        _event(decline_code="MANDATE_PAUSED"),
        _event(decline_code="NON_REVOCABLE_HARD_DECLINE", is_revocable=False),
        _event(decline_code="MANDATE_EXPIRED"),
        _event(decline_code="AFA_REQUIRED", amount=16000),
        _event(decline_code="AFA_REQUIRED", amount=14000),   # borderline -> Tier-2
        _event(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=22),  # ambiguous -> Tier-2
    ]

    mock_tier2 = Tier2Result(
        action="SCHEDULE_POST_SALARY",
        message_hinglish="Test message",
        rationale="Test",
        confidence=0.7,
    )

    patches = _mock_razorpay()
    for p in patches:
        p.start()

    with mock.patch("core.orchestrator.tier2_reason", return_value=mock_tier2):
        result = await process_batch(events)

    for p in patches:
        p.stop()

    tier1_pct = result.metrics.tier1_pct
    assert 60.0 <= tier1_pct <= 80.0, f"Tier-1 rate {tier1_pct}% outside expected range 60–80%"
    assert result.metrics.total_records == 10


@pytest.mark.asyncio
async def test_deliberate_compliance_violation_caught():
    """
    Inject a non-revocable mandate and force Tier-2 to propose a retry.
    The compliance gate must catch it and redirect to ESCALATE_TO_HUMAN.
    """
    event = _event(
        decline_code="NON_REVOCABLE_HARD_DECLINE",
        is_revocable=False,
        amount=45000,
        attempt_number=2,
    )

    # Force Tier-1 to route to Tier-2 (we cannot easily, so force via a borderline code)
    # Instead: directly test via a code the gate catches regardless of tier
    mock_tier2 = Tier2Result(
        action="RETRY_AFTER_BACKOFF",   # Illegal for non-revocable
        message_hinglish="Retry kar lo",
        rationale="Attempting retry",
        confidence=0.6,
    )

    patches = _mock_razorpay()
    for p in patches:
        p.start()

    # Patch Tier-1 to be ambiguous so Tier-2 is called
    with mock.patch("core.orchestrator.tier1_classify") as mock_t1, \
         mock.patch("core.orchestrator.tier2_reason", return_value=mock_tier2):
        from models.recovery_decision import Tier1Result
        mock_t1.return_value = Tier1Result(action=None, is_ambiguous=True, reason="forced_test")
        result = await process_batch([event])

    for p in patches:
        p.stop()

    decision = result.decisions[0]
    assert decision.proposed_action == "RETRY_AFTER_BACKOFF"
    assert decision.compliance_result.violation_blocked is True
    assert decision.final_action == "ESCALATE_TO_HUMAN"
    assert decision.outcome == "escalated"
    assert result.metrics.compliance_violations_caught == 1
    assert result.metrics.compliance_violations_executed == 0


@pytest.mark.asyncio
async def test_audit_log_one_entry_per_mandate():
    """Every record in the batch must produce exactly one audit entry."""
    from models.db import AsyncSessionLocal
    from models.db import AuditLogORM
    from sqlalchemy import select

    events = [_event(decline_code="BANK_TECHNICAL_DECLINE") for _ in range(5)]
    patches = _mock_razorpay()
    for p in patches:
        p.start()

    result = await process_batch(events)
    for p in patches:
        p.stop()

    async with AsyncSessionLocal() as db:
        for event in events:
            stmt = select(AuditLogORM).where(AuditLogORM.mandate_id == event.mandate_id)
            entries = (await db.execute(stmt)).scalars().all()
            assert len(entries) == 1, f"Expected 1 audit entry for {event.mandate_id}, got {len(entries)}"
