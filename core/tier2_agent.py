# core/tier2_agent.py
"""
Tier-2: Groq-powered reasoning agent for ambiguous mandate cases.

INVARIANT: This file must never be imported by core.tier1_engine or
core.compliance_gate. All output is constrained to ALLOWED_ACTIONS via
the Pydantic Tier2Result schema; any failure escalates to a human.
"""
import json
import logging
import os
from pydantic import ValidationError
from groq import APIError, APITimeoutError

from models.mandate_event import MandateEvent
from models.recovery_decision import Tier2Result
from services.groq_client import get_groq_client
from config.loader import load_config

logger = logging.getLogger(__name__)

_cfg = load_config()


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


async def tier2_reason(event: MandateEvent) -> Tier2Result:
    """
    Call Groq to reason about an ambiguous mandate event.
    Returns Tier2Result. Falls back to ESCALATE_TO_HUMAN on any failure.
    """
    model = os.getenv("GROQ_MODEL_TIER2", "openai/gpt-oss-120b")
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
