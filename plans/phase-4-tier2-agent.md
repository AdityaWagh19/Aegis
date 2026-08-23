# Phase 4: Tier-2 Groq Agent

> **Status:** [ ] Not started
> **Estimated duration:** Days 6–7
> **Depends on:** Phase 1 (models, config), Phase 3 (compliance gate must be complete before wiring Tier-2 output through it)

---

## Objective

Implement the Groq-powered reasoning agent that handles ambiguous mandate cases (~25–35% of batch). The agent must produce structured JSON output constrained to the fixed action allow-list, draft Hinglish recovery messages, provide confidence scores and alternatives, and fall back to `ESCALATE_TO_HUMAN` on any malformed or unexpected output.

---

## Scope

- `core/tier2_agent.py` — async `tier2_reason(event: MandateEvent) -> Tier2Result`
- `tests/unit/test_tier2_schema.py` — schema validation, allow-list enforcement, fallback behaviour
- Hinglish message templates seeded into the system prompt

---

## Design Decisions and Rationale

**D1 — Groq with tool calling (function calling), not plain text completion.**
The agent uses Groq's function-calling interface to return structured JSON. This is more reliable than prompting for JSON in a text response and then parsing it. The tool schema defines `action` as an enum of `ALLOWED_ACTIONS`, `message_hinglish` as a required string, `confidence` as a float, and `alternatives_considered` as an optional list.

**D2 — Pydantic validation is the final enforcement layer.**
After Groq returns a tool call result, the JSON is parsed into `Tier2Result` via Pydantic. Any `action` value outside the `Literal` enum raises `ValidationError`. The `except ValidationError` block in `tier2_reason()` catches this and returns the fallback result. The LLM cannot invent a new action at runtime — Pydantic enforces it at parse time.

**D3 — Fallback on any failure returns `ESCALATE_TO_HUMAN`.**
If Groq returns a non-tool-call response, returns malformed JSON, raises a `groq.APIError`, times out, or returns an action outside the allow-list, the fallback is always `ESCALATE_TO_HUMAN` with `confidence=0.0` and `rationale="tier2_failure"`. This is the safest possible outcome — a human reviews the case rather than an invalid action executing.

**D4 — `temperature=0.1` for action selection, `temperature=0.2` for message drafting.**
Action selection requires determinism — a low temperature reduces variance in which action is chosen. Hinglish message drafting benefits from slight variety (temperature 0.2) so repeated paused-mandate cases produce different wording.

**D5 — A two-step prompt: classify then draft.**
The agent first classifies the action using a tool call (temperature=0.1). If the action involves a customer message (`SEND_HINGLISH_NUDGE`, `SEND_UPI_INTENT_PUSH`, `SEND_MANDATE_RENEWAL_LINK`), a second completion drafts the Hinglish message (temperature=0.2). This reduces token usage on cases that escalate or need no message.

**D6 — System prompt seeds the taxonomy and Hinglish examples.**
The system prompt includes the six failure categories, the action allow-list, and three Hinglish example messages. This dramatically reduces hallucination of invalid actions or poor Hinglish quality.

---

## Sequential Implementation Tasks

### Task 4.1 — Create Groq client wrapper `services/groq_client.py`

```python
# services/groq_client.py
import os
from groq import AsyncGroq

_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set.")
        _client = AsyncGroq(api_key=api_key)
    return _client
```

### Task 4.2 — Define the Groq tool schema

```python
# core/tier2_agent.py  (Tool schema constant)

RECOVER_MANDATE_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_recovery_action",
        "description": (
            "Analyse a failed UPI Autopay or e-NACH mandate event and propose "
            "the most appropriate recovery action from the allowed list. "
            "Also provide a Hinglish customer message if the action involves customer communication."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "RETRY_AFTER_BACKOFF",
                        "SCHEDULE_POST_SALARY",
                        "SEND_UPI_INTENT_PUSH",
                        "SEND_MANDATE_RENEWAL_LINK",
                        "SEND_HINGLISH_NUDGE",
                        "ESCALATE_TO_HUMAN",
                        "NO_ACTION_MONITORING",
                    ],
                    "description": "The recovery action to take. Must be exactly one of the listed values.",
                },
                "message_hinglish": {
                    "type": "string",
                    "description": (
                        "A short (1–2 sentence) Hinglish (Hindi-English code-mixed) message "
                        "to send to the customer. Required for all actions except ESCALATE_TO_HUMAN "
                        "and NO_ACTION_MONITORING. Use loss-aversion framing."
                    ),
                },
                "rationale": {
                    "type": "string",
                    "description": "Brief technical explanation of why this action was chosen (1–3 sentences).",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence in the proposed action (0.0 = very uncertain, 1.0 = certain).",
                },
                "alternatives_considered": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Other actions considered before choosing the primary action.",
                },
            },
            "required": ["action", "message_hinglish", "rationale", "confidence"],
        },
    },
}
```

### Task 4.3 — Define the system prompt

```python
# core/tier2_agent.py  (System prompt constant)

SYSTEM_PROMPT = """You are Aegis, a compliant UPI Autopay and e-NACH mandate failure recovery agent for India.

## Your Role
Analyse failed mandate events and propose recovery actions. You MUST use the propose_recovery_action tool.

## The Six Failure Categories
| Code | Root Cause | Default Action |
|---|---|---|
| INSUFFICIENT_FUNDS | Debit attempted before salary credit | SCHEDULE_POST_SALARY |
| AFA_REQUIRED | Silent debit above Rs. 15,000 NPCI threshold | SEND_UPI_INTENT_PUSH |
| MANDATE_PAUSED | Customer paused via RBI 24h pre-debit notice | SEND_HINGLISH_NUDGE |
| BANK_TECHNICAL_DECLINE | Bank timeout or downtime | RETRY_AFTER_BACKOFF |
| NON_REVOCABLE_HARD_DECLINE | Loan EMI, 2nd hard decline | ESCALATE_TO_HUMAN |
| MANDATE_EXPIRED | e-mandate validity window lapsed | SEND_MANDATE_RENEWAL_LINK |

## Compliance Rules (MANDATORY)
1. NEVER propose RETRY_AFTER_BACKOFF or SCHEDULE_POST_SALARY if is_revocable=false and decline_code=NON_REVOCABLE_HARD_DECLINE.
2. NEVER propose a retry action if attempt_number has reached the maximum (UPI_AUTOPAY: 3, ENACH: 2).
3. NEVER propose a retry action if amount > 15000 for general mandates (AFA rule) — use SEND_UPI_INTENT_PUSH instead.
4. NEVER propose a retry action if decline_code=MANDATE_PAUSED — use SEND_HINGLISH_NUDGE or ESCALATE_TO_HUMAN.

## Hinglish Message Examples
- MANDATE_PAUSED: "Aapka [service] subscription abhi bhi active hai! Sirf ek click se payment complete karein — aaj hi!"
- AFA_REQUIRED: "Aapki payment ke liye ek-baar approval chahiye. Neeche diye link pe click karein — 2 minute ka kaam!"
- INSUFFICIENT_FUNDS: "Salary aane ke baad aapka payment automatically process ho jayega. Koi action ki zaroorat nahi!"

## Important
You are advising a collections system. Be precise, concise, and always use the tool. Never decline to use the tool.
"""
```

### Task 4.4 — Implement `core/tier2_agent.py`

```python
# core/tier2_agent.py
import json
import logging
from pydantic import ValidationError
from groq import APIError, APITimeoutError

from models.mandate_event import MandateEvent
from models.recovery_decision import Tier2Result
from services.groq_client import get_groq_client
from config.loader import load_config

logger = logging.getLogger(__name__)

_cfg = load_config()
MODEL = _cfg.__dict__.get("groq_model_tier2", "llama-3.3-70b-versatile")

# Tier2Result validation model (import from models/ but defined here for clarity)
_FALLBACK_RESULT = Tier2Result(
    action="ESCALATE_TO_HUMAN",
    message_hinglish="Aapke mandate ke baare mein hamare team se baat karein.",
    rationale="tier2_failure",
    confidence=0.0,
    alternatives_considered=None,
)


async def tier2_reason(event: MandateEvent) -> Tier2Result:
    """
    Call Groq (llama-3.3-70b-versatile) to reason about an ambiguous mandate event.
    Returns Tier2Result. Falls back to ESCALATE_TO_HUMAN on any failure.
    """
    import os
    model = os.getenv("GROQ_MODEL_TIER2", "llama-3.3-70b-versatile")
    client = get_groq_client()

    user_message = _build_user_message(event)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            tools=[RECOVER_MANDATE_TOOL],
            tool_choice={"type": "function", "function": {"name": "propose_recovery_action"}},
            temperature=0.1,
            max_tokens=512,
            timeout=30.0,
        )

        message = response.choices[0].message
        if not message.tool_calls:
            logger.warning("Tier-2: Groq returned no tool call for mandate_id=%s", event.mandate_id)
            return _fallback(event, "no_tool_call_returned")

        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)

        try:
            result = Tier2Result(**args)
            logger.info(
                "Tier-2: mandate_id=%s action=%s confidence=%.2f",
                event.mandate_id, result.action, result.confidence
            )
            return result
        except ValidationError as ve:
            logger.warning(
                "Tier-2: Pydantic validation failed for mandate_id=%s: %s",
                event.mandate_id, ve
            )
            return _fallback(event, "pydantic_validation_failed")

    except (APIError, APITimeoutError) as e:
        logger.error("Tier-2: Groq API error for mandate_id=%s: %s", event.mandate_id, e)
        return _fallback(event, "groq_api_error")
    except json.JSONDecodeError as e:
        logger.error("Tier-2: JSON decode error for mandate_id=%s: %s", event.mandate_id, e)
        return _fallback(event, "json_decode_error")
    except Exception as e:
        logger.error("Tier-2: Unexpected error for mandate_id=%s: %s", event.mandate_id, e, exc_info=True)
        return _fallback(event, "unexpected_error")


def _fallback(event: MandateEvent, reason: str) -> Tier2Result:
    logger.warning("Tier-2 fallback: mandate_id=%s reason=%s", event.mandate_id, reason)
    return Tier2Result(
        action="ESCALATE_TO_HUMAN",
        message_hinglish="Aapke mandate ke baare mein hamare team se baat karein.",
        rationale=f"tier2_failure:{reason}",
        confidence=0.0,
        alternatives_considered=None,
    )


def _build_user_message(event: MandateEvent) -> str:
    return f"""Mandate failure event to analyse:

mandate_id: {event.mandate_id}
customer_id: {event.customer_id}
amount: Rs. {event.amount:,}
mandate_type: {event.mandate_type}
product_category: {event.product_category or 'unknown'}
decline_code: {event.decline_code}
days_since_salary_credit: {event.days_since_salary_credit}
prior_bounce_count: {event.prior_bounce_count}
is_revocable: {event.is_revocable}
attempt_number: {event.attempt_number}

Propose the appropriate recovery action using the propose_recovery_action tool."""
```

### Task 4.5 — Implement `tests/unit/test_tier2_schema.py`

```python
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
async def test_tier2_fallback_on_api_error():
    """Groq API errors must produce ESCALATE_TO_HUMAN fallback."""
    from core.tier2_agent import tier2_reason
    from groq import APIError

    with mock.patch("core.tier2_agent.get_groq_client") as mock_client:
        instance = mock_client.return_value
        instance.chat.completions.create = mock.AsyncMock(
            side_effect=APIError("Rate limit", response=mock.MagicMock(), body={})
        )
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
```

### Task 4.6 — Smoke test against live Groq API (manual, Day 7)

```python
# scripts/smoke_test_tier2.py
"""Run manually to verify Groq connectivity and response quality."""
import asyncio
from datetime import datetime, timezone
from models.mandate_event import MandateEvent
from core.tier2_agent import tier2_reason

TEST_CASES = [
    dict(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=20, prior_bounce_count=2, amount=8000),
    dict(decline_code="AFA_REQUIRED", amount=14200, mandate_type="UPI_AUTOPAY"),
    dict(decline_code="NON_REVOCABLE_HARD_DECLINE", is_revocable=False, amount=45000),
]

async def run():
    for case in TEST_CASES:
        event = MandateEvent(
            customer_id="SMOKE-001", mandate_type="UPI_AUTOPAY",
            product_category="subscription", days_since_salary_credit=5,
            prior_bounce_count=0, is_revocable=True, attempt_number=1,
            timestamp=datetime.now(timezone.utc), **case
        )
        result = await tier2_reason(event)
        print(f"\n--- {event.decline_code} ---")
        print(f"Action:     {result.action}")
        print(f"Confidence: {result.confidence}")
        print(f"Hinglish:   {result.message_hinglish}")
        print(f"Rationale:  {result.rationale}")

asyncio.run(run())
```

Run with: `python scripts/smoke_test_tier2.py`

---

## Validation Strategy

1. `pytest tests/unit/test_tier2_schema.py -v` — all tests pass without calling Groq API.
2. `python scripts/smoke_test_tier2.py` — 3 test cases return valid `Tier2Result` objects with sensible Hinglish messages. Verify manually that actions match the expected taxonomy.
3. Inject a deliberate bad action in the tool response and verify the fallback triggers.

---

## Acceptance Criteria

- [ ] `pytest tests/unit/test_tier2_schema.py -v` exits with code 0.
- [ ] `test_invalid_action_rejected_by_pydantic` passes — Pydantic blocks invalid actions.
- [ ] `test_all_allowed_actions_accepted` passes — all 7 allowed actions are valid `Tier2Result` inputs.
- [ ] All three fallback tests pass (`no_tool_call`, `invalid_action`, `api_error`).
- [ ] `python scripts/smoke_test_tier2.py` completes without exception and returns plausible actions.
- [ ] Hinglish messages in smoke test output are grammatically reasonable and use code-mixing.
- [ ] Average Groq response latency across 3 smoke test calls is < 3,000ms.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| Groq API key not set | High initially | `get_groq_client()` raises `RuntimeError` with clear message |
| Model rate limit hit | Medium during batch tests | Use `llama-3.1-8b-instant` (60 req/min) for development |
| Tool call not returned (model hallucinates plain text) | Low with `tool_choice=forced` | Fallback handler catches `message.tool_calls is None` |
| Hinglish quality poor for some categories | Medium | System prompt seeds three Hinglish examples; review smoke test output |

---

## Deliverables

- `services/groq_client.py` — singleton async Groq client
- `core/tier2_agent.py` — `tier2_reason()`, system prompt, tool schema, fallback handler
- `tests/unit/test_tier2_schema.py` — 8 schema/fallback tests (no live API calls)
- `scripts/smoke_test_tier2.py` — manual connectivity test

---

## Documentation Updates

- Check off Phase 4 tasks in `project-context/tasks.md`
- Record smoke test results (action quality, latency) in `project-context/progress.md` Day 6/7
- Update `plans/overview.md` Phase 4 status: `[x]`
