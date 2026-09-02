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
from core.config import load_config

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


async def tier2_reason(event: MandateEvent, tenant_id: str = "default", tier2_budget: int = 10) -> Tier2Result:
    """
    Call Groq to reason about an ambiguous mandate event.
    Returns Tier2Result. Falls back to ESCALATE_TO_HUMAN on any failure.
    Phase 9: checks rate limiter budget, selects model, records Prometheus metrics.
    """
    import time
    from core.tier2_rate_limiter import select_model_for_tenant
    from observability.metrics import tier2_calls_total, groq_latency_seconds

    model = await select_model_for_tenant(tenant_id, tier2_budget)

    if model is None:
        logger.warning("Tier-2 skipped (budget exhausted): mandate_id=%s", event.mandate_id)
        return Tier2Result(
            action="ESCALATE_TO_HUMAN",
            message_hinglish="Hamare system mein abhi thoda busy hai. Agent se baat karein.",
            rationale="tier2_budget_exhausted",
            confidence=0.0,
        )

    client = get_groq_client()
    user_message = _build_user_message(event)
    start = time.perf_counter()

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
            latency = time.perf_counter() - start
            groq_latency_seconds.labels(tenant_id=tenant_id, model=model).observe(latency)
            tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="fallback").inc()
            return _fallback(event, "no_tool_call_returned")

        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)

        try:
            result = Tier2Result(**args)
            latency = time.perf_counter() - start
            groq_latency_seconds.labels(tenant_id=tenant_id, model=model).observe(latency)
            tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="success").inc()
            logger.info(
                "Tier-2: mandate_id=%s action=%s confidence=%.2f model=%s",
                event.mandate_id, result.action, result.confidence, model
            )
            return result
        except ValidationError as ve:
            logger.warning(
                "Tier-2: Pydantic validation failed for mandate_id=%s: %s",
                event.mandate_id, ve
            )
            latency = time.perf_counter() - start
            groq_latency_seconds.labels(tenant_id=tenant_id, model=model).observe(latency)
            tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="fallback").inc()
            return _fallback(event, "pydantic_validation_failed")

    except (APIError, APITimeoutError) as e:
        logger.error("Tier-2: Groq API error for mandate_id=%s: %s", event.mandate_id, e)
        latency = time.perf_counter() - start
        groq_latency_seconds.labels(tenant_id=tenant_id, model=model).observe(latency)
        tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="error").inc()
        return _fallback(event, "groq_api_error")
    except json.JSONDecodeError as e:
        logger.error("Tier-2: JSON decode error for mandate_id=%s: %s", event.mandate_id, e)
        tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="error").inc()
        return _fallback(event, "json_decode_error")
    except Exception as e:
        logger.error("Tier-2: Unexpected error for mandate_id=%s: %s", event.mandate_id, e, exc_info=True)
        tier2_calls_total.labels(tenant_id=tenant_id, model=model, result="error").inc()
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
