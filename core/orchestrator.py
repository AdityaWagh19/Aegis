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
from audit.log import audit_log

logger = logging.getLogger(__name__)

_gate = ComplianceGate()


async def process_batch(events: list[MandateEvent]) -> BatchResult:
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
            decision = await _process_single(event, db)
            decisions.append(decision)

    metrics = _compute_metrics(events, decisions)
    return BatchResult(
        batch_id=batch_id,
        status="complete",
        metrics=metrics,
        decisions=decisions,
    )


async def _process_single(event: MandateEvent, db: AsyncSession) -> RecoveryDecision:
    # --- Tier-1 ---
    tier1_result = tier1_classify(event)

    if tier1_result.is_ambiguous:
        # --- Tier-2 ---
        tier2_result = await tier2_reason(event)
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

    # --- Action Executor ---
    outcome, razorpay_response = await execute(event, final_action, hinglish_message)

    # --- Escalation Queue ---
    if outcome == "escalated":
        await _add_to_review_queue(event, compliance_result.violation_rule, db)

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
    await audit_log.append(event, decision, db)

    return decision


async def _add_to_review_queue(event: MandateEvent, compliance_rule: str | None, db: AsyncSession):
    import uuid
    from datetime import datetime, timezone
    item = HumanReviewQueueORM(
        review_id=str(uuid.uuid4()),
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
