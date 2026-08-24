# tests/unit/test_tier2_schema.py
"""
Tests Tier-2 output schema validation and fallback behaviour.
These tests do NOT call the Groq API — they test the validation and
fallback logic in isolation using mocks.
"""
import pytest
import unittest.mock as mock
from pydantic import ValidationError
from datetime import datetime, timezone

from models.mandate_event import MandateEvent, ALLOWED_ACTIONS
from models.recovery_decision import Tier2Result


def _event(**kwargs) -> MandateEvent:
    defaults = dict(
        customer_id="TEST-001", amount=5000, mandate_type="UPI_AUTOPAY",
        product_category="subscription", decline_code="INSUFFICIENT_FUNDS",
        days_since_salary_credit=5, prior_bounce_count=0, is_revocable=True,
        attempt_number=1, timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return MandateEvent(**defaults)


def test_valid_tier2_result_accepted():
    result = Tier2Result(
        action="ESCALATE_TO_HUMAN",
        message_hinglish="Test message.",
        rationale="Test rationale.",
        confidence=0.85,
    )
    assert result.action == "ESCALATE_TO_HUMAN"
    assert result.confidence == 0.85


def test_invalid_action_rejected_by_pydantic():
    """Any action outside ALLOWED_ACTIONS must raise ValidationError."""
    with pytest.raises(ValidationError):
        Tier2Result(
            action="INVENT_NEW_ACTION",
            message_hinglish="Test",
            rationale="Test",
            confidence=0.8,
        )


def test_all_allowed_actions_accepted():
    """Every action in ALLOWED_ACTIONS must be accepted by Tier2Result."""
    for action in ALLOWED_ACTIONS:
        result = Tier2Result(
            action=action,
            message_hinglish="Test",
            rationale="Test",
            confidence=0.7,
        )
        assert result.action == action


@pytest.mark.asyncio
async def test_tier2_fallback_on_no_tool_call():
    """When Groq returns no tool call, fallback to ESCALATE_TO_HUMAN."""
    from core.tier2_agent import tier2_reason

    mock_response = mock.MagicMock()
    mock_response.choices[0].message.tool_calls = None

    with mock.patch("core.tier2_agent.get_groq_client") as mock_client:
        instance = mock_client.return_value
        instance.chat.completions.create = mock.AsyncMock(return_value=mock_response)
        result = await tier2_reason(_event())

    assert result.action == "ESCALATE_TO_HUMAN"
    assert result.confidence == 0.0
    assert "tier2_failure" in result.rationale


@pytest.mark.asyncio
async def test_tier2_fallback_on_invalid_action():
    """When Groq returns an action outside ALLOWED_ACTIONS, fallback."""
    from core.tier2_agent import tier2_reason
    import json

    mock_tool_call = mock.MagicMock()
    mock_tool_call.function.arguments = json.dumps({
        "action": "DO_SOMETHING_ILLEGAL",
        "message_hinglish": "Test",
        "rationale": "Test",
        "confidence": 0.9,
    })
    mock_response = mock.MagicMock()
    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    with mock.patch("core.tier2_agent.get_groq_client") as mock_client:
        instance = mock_client.return_value
        instance.chat.completions.create = mock.AsyncMock(return_value=mock_response)
        result = await tier2_reason(_event())

    assert result.action == "ESCALATE_TO_HUMAN"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_tier2_fallback_on_malformed_output():
    """If LLM returns malformed (non-JSON) tool arguments, fall back to ESCALATE_TO_HUMAN."""
    from core.tier2_agent import tier2_reason

    mock_tool_call = mock.MagicMock()
    mock_tool_call.function.arguments = "not valid json"
    mock_response = mock.MagicMock()
    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    with mock.patch("core.tier2_agent.get_groq_client") as mock_client:
        instance = mock_client.return_value
        instance.chat.completions.create = mock.AsyncMock(return_value=mock_response)
        result = await tier2_reason(_event())

    assert result.action == "ESCALATE_TO_HUMAN"
    assert "tier2_failure" in result.rationale


@pytest.mark.asyncio
async def test_tier2_fallback_on_api_error():
    """Groq API errors must produce ESCALATE_TO_HUMAN fallback."""
    from core.tier2_agent import tier2_reason
    import httpx
    from groq import APIError

    # groq 0.9.0 signature: APIError(message, request, *, body)
    api_error = APIError(
        "Rate limit", httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"), body={}
    )
    with mock.patch("core.tier2_agent.get_groq_client") as mock_client:
        instance = mock_client.return_value
        instance.chat.completions.create = mock.AsyncMock(side_effect=api_error)
        result = await tier2_reason(_event())

    assert result.action == "ESCALATE_TO_HUMAN"
    assert "tier2_failure" in result.rationale


@pytest.mark.asyncio
async def test_tier2_success_returns_correct_action():
    """When Groq returns a valid tool call, the result is parsed correctly."""
    from core.tier2_agent import tier2_reason
    import json

    mock_tool_call = mock.MagicMock()
    mock_tool_call.function.arguments = json.dumps({
        "action": "SCHEDULE_POST_SALARY",
        "message_hinglish": "Salary aane ke baad payment ho jayega.",
        "rationale": "INSUFFICIENT_FUNDS with days_since_salary_credit=3.",
        "confidence": 0.88,
        "alternatives_considered": ["RETRY_AFTER_BACKOFF"],
    })
    mock_response = mock.MagicMock()
    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    with mock.patch("core.tier2_agent.get_groq_client") as mock_client:
        instance = mock_client.return_value
        instance.chat.completions.create = mock.AsyncMock(return_value=mock_response)
        result = await tier2_reason(_event(decline_code="INSUFFICIENT_FUNDS"))

    assert result.action == "SCHEDULE_POST_SALARY"
    assert result.confidence == 0.88
    assert result.alternatives_considered == ["RETRY_AFTER_BACKOFF"]
