# core/orchestrator.py
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from models.mandate_event import MandateEvent
from models.recovery_decision import (
    RecoveryDecision, BatchResult, BatchMetrics
)
from models.db import (
    MandateEventORM, RecoveryDecisionORM, HumanReviewQueueORM, AsyncSessionLocal
)
from core.tier1_engine import classify as tier1_classify
from core.tier2_agent import tier2_reason
from core.compliance_gate import ComplianceGate
from core.action_executor import execute
from core.audit import audit_log
from observability.metrics import recovery_actions_total, compliance_violations_total

logger = logging.getLogger(__name__)

_gate = ComplianceGate()


async def process_batch(events: list[MandateEvent], tenant_id: str = "default") -> BatchResult:
    """
    Main entry point for batch processing.
    Wires Tier-1 -> Tier-2 (if needed) -> Compliance Gate -> Action Executor -> Audit Log.
    Returns BatchResult with all decisions and computed metrics.

    Performance note: Tier-2 Groq calls are sequential within this function.
    Worst-case: 30% Tier-2 on a 200-record batch = 60 sequential ~1s calls = ~60s.
    For production throughput, Phase 9 moves processing to async ARQ workers
    (one worker job per webhook event) and uses asyncio.gather() for parallel calls.
    """
    batch_id = str(uuid.uuid4())
    decisions: list[RecoveryDecision] = []

    async with AsyncSessionLocal() as db:
        for event in events:
            event.batch_id = batch_id
            await _persist_event(event, db, tenant_id=tenant_id)
            decision = await _process_single(event, db, tenant_id=tenant_id)
            decisions.append(decision)

    metrics = _compute_metrics(events, decisions)
    return BatchResult(
        batch_id=batch_id,
        status="complete",
        metrics=metrics,
        decisions=decisions,
    )


async def process_single_with_config(
    event: MandateEvent,
    compliance_cfg,
    razorpay_client,
    tenant_id: str,
    db: AsyncSession,
) -> RecoveryDecision:
    """
    Per-tenant version of _process_single() (Phase 9).
    Uses injected compliance_cfg and razorpay_client instead of module-level singletons.
    """
    gate = ComplianceGate(config=compliance_cfg)
    event.batch_id = event.batch_id or f"webhook_{tenant_id}"

    await _persist_event(event, db, tenant_id=tenant_id)

    # --- Tier-1 (with per-tenant config) ---
    tier1_result = tier1_classify(event, config=compliance_cfg)

    if tier1_result.is_ambiguous:
        # --- Tier-2 (with rate limiter) ---
        budget = getattr(compliance_cfg, "tier2_budget_per_minute", 10)
        tier2_result = await tier2_reason(event, tenant_id=tenant_id, tier2_budget=budget)
        proposed_action = tier2_result.action
        tier_decided = 2
        rationale = tier2_result.rationale
        confidence = tier2_result.confidence
        hinglish_message = tier2_result.message_hinglish
        alternatives = tier2_result.alternatives_considered
    else:
        proposed_action = tier1_result.action
        tier_decided = 1
        rationale = tier1_result.reason
        confidence = None
        hinglish_message = None
        alternatives = None

    # --- Compliance Gate (always runs, per-tenant) ---
    compliance_result = gate.check(event, proposed_action)
    final_action = compliance_result.final_action

    if compliance_result.violation_blocked:
        logger.warning(
            "Compliance violation blocked: mandate_id=%s proposed=%s rule=%s final=%s tenant_id=%s",
            event.mandate_id, proposed_action,
            compliance_result.violation_rule, final_action, tenant_id
        )
        compliance_violations_total.labels(
            tenant_id=tenant_id, violation_rule=compliance_result.violation_rule or "unknown"
        ).inc()

    # --- Action Executor (with per-tenant Razorpay client) ---
    outcome, razorpay_response = await execute(
        event=event,
        final_action=final_action,
        hinglish_message=hinglish_message,
        razorpay_client=razorpay_client,
    )

    # Prometheus counter
    recovery_actions_total.labels(
        tenant_id=tenant_id, action=final_action, outcome=outcome
    ).inc()

    # --- Escalation Queue ---
    if outcome == "escalated":
        await _add_to_review_queue(event, compliance_result.violation_rule, db, tenant_id=tenant_id)

    decision = RecoveryDecision(
        mandate_id=event.mandate_id,
        tier_that_decided=tier_decided,
        proposed_action=proposed_action,
        compliance_result=compliance_result,
        final_action=final_action,
        outcome=outcome,
        rationale=rationale,
        confidence=confidence,
        hinglish_message=hinglish_message,
        alternatives_considered=alternatives,
        razorpay_response=razorpay_response,
    )

    # --- Audit Log (with tenant attribution) ---
    await audit_log.append(event, decision, db, tenant_id=tenant_id)

    return decision


async def _persist_event(event: MandateEvent, db: AsyncSession, tenant_id: str = "default") -> None:
    """
    Persist the MandateEvent before its decision is recorded.

    PostgreSQL enforces the FK from human_review_queue / recovery_decisions to
    mandate_events — SQLite silently ignores it, which is why this only
    surfaced at deployment. merge() keeps re-uploads of the same mandate id
    idempotent.
    """
    await db.merge(
        MandateEventORM(
            mandate_id=event.mandate_id,
            tenant_id=tenant_id,
            customer_id=event.customer_id,
            amount=event.amount,
            mandate_type=event.mandate_type,
            product_category=event.product_category,
            decline_code=event.decline_code,
            days_since_salary_credit=event.days_since_salary_credit,
            prior_bounce_count=event.prior_bounce_count,
            is_revocable=event.is_revocable,
            attempt_number=event.attempt_number,
            event_timestamp=event.timestamp,
            batch_id=event.batch_id or "",
            is_held_out=event.is_held_out,
            correct_action=event.correct_action,
        )
    )
    await db.commit()


async def _process_single(event: MandateEvent, db: AsyncSession, tenant_id: str = "default") -> RecoveryDecision:
    # --- Tier-1 ---
    tier1_result = tier1_classify(event)

    if tier1_result.is_ambiguous:
        # --- Tier-2 ---
        tier2_result = await tier2_reason(event, tenant_id=tenant_id)
        proposed_action = tier2_result.action
        tier_decided = 2
        rationale = tier2_result.rationale
        confidence = tier2_result.confidence
        hinglish_message = tier2_result.message_hinglish
        alternatives = tier2_result.alternatives_considered
    else:
        proposed_action = tier1_result.action
        tier_decided = 1
        rationale = tier1_result.reason
        confidence = None
        hinglish_message = None
        alternatives = None

    # --- Compliance Gate (always runs) ---
    compliance_result = _gate.check(event, proposed_action)
    final_action = compliance_result.final_action

    if compliance_result.violation_blocked:
        logger.warning(
            "Compliance violation blocked: mandate_id=%s proposed=%s rule=%s final=%s",
            event.mandate_id, proposed_action,
            compliance_result.violation_rule, final_action
        )
        compliance_violations_total.labels(
            tenant_id=tenant_id, violation_rule=compliance_result.violation_rule or "unknown"
        ).inc()

    # --- Action Executor ---
    outcome, razorpay_response = await execute(event, final_action, hinglish_message)

    # Prometheus counter
    recovery_actions_total.labels(
        tenant_id=tenant_id, action=final_action, outcome=outcome
    ).inc()

    # --- Escalation Queue ---
    if outcome == "escalated":
        await _add_to_review_queue(event, compliance_result.violation_rule, db, tenant_id=tenant_id)

    decision = RecoveryDecision(
        mandate_id=event.mandate_id,
        tier_that_decided=tier_decided,
        proposed_action=proposed_action,
        compliance_result=compliance_result,
        final_action=final_action,
        outcome=outcome,
        rationale=rationale,
        confidence=confidence,
        hinglish_message=hinglish_message,
        alternatives_considered=alternatives,
        razorpay_response=razorpay_response,
    )

    # --- Audit Log (every decision produces exactly one entry) ---
    await audit_log.append(event, decision, db, tenant_id=tenant_id)

    return decision


async def _add_to_review_queue(event: MandateEvent, compliance_rule: str | None, db: AsyncSession, tenant_id: str = "default"):
    import uuid
    from datetime import datetime, timezone
    item = HumanReviewQueueORM(
        review_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        mandate_id=event.mandate_id,
        reason=compliance_rule or "tier2_escalation",
        compliance_rule=compliance_rule,
    )
    db.add(item)
    await db.commit()


def _compute_metrics(events: list[MandateEvent], decisions: list[RecoveryDecision]) -> BatchMetrics:
    total = len(decisions)
    tier1_count = sum(1 for d in decisions if d.tier_that_decided == 1)
    tier2_count = total - tier1_count
    violations_caught = sum(1 for d in decisions if d.compliance_result.violation_blocked)
    violations_executed = 0   # By design: a blocked violation never executes

    # Rs. recovered = sum of amounts where outcome == "executed"
    amount_map = {e.mandate_id: e.amount for e in events}
    rs_recovered = sum(
        amount_map.get(d.mandate_id, 0)
        for d in decisions if d.outcome == "executed"
    )
    rs_at_risk = sum(amount_map.values())
    recovery_rate = rs_recovered / rs_at_risk if rs_at_risk > 0 else 0.0

    return BatchMetrics(
        total_records=total,
        tier1_count=tier1_count,
        tier2_count=tier2_count,
        tier1_pct=round(tier1_count / total * 100, 1) if total > 0 else 0.0,
        recovery_rate=round(recovery_rate, 4),
        rs_recovered=rs_recovered,
        rs_at_risk=rs_at_risk,
        compliance_violations_caught=violations_caught,
        compliance_violations_executed=violations_executed,
    )
