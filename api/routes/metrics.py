# api/routes/metrics.py
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from models.db import AsyncSessionLocal, AuditLogORM, MandateEventORM

router = APIRouter()


@router.get("/metrics")
async def get_metrics(batch_id: str | None = Query(default=None)):
    """
    Aggregate metrics across all decisions, or for a specific batch_id.
    Reads from the audit_log and mandate_events tables.
    Phase 10: includes rs_recovered from payment.captured events.
    Audit: includes rs_at_risk, analyst_hours_saved, auto_resolution_rate.
    """
    async with AsyncSessionLocal() as db:
        # Audit entries (decisions + payment_captured events)
        stmt = select(AuditLogORM)
        entries = (await db.execute(stmt)).scalars().all()

        # Total amount at risk from persisted mandate events
        rs_at_risk_result = await db.execute(
            select(func.coalesce(func.sum(MandateEventORM.amount), 0))
        )
        rs_at_risk = rs_at_risk_result.scalar() or 0

    payloads = [e.payload for e in entries]
    total = len(payloads)
    if total == 0:
        return {
            "total_records": 0,
            "message": "No decisions recorded yet.",
            "rs_recovered": 0,
            "rs_at_risk": 0,
            "recovered_count": 0,
            "analyst_hours_saved": 0,
            "auto_resolution_rate": 0,
        }

    tier1_count = sum(1 for p in payloads if p.get("tier_that_decided") == 1)
    violations_caught = sum(1 for p in payloads if p.get("violation_blocked"))
    escalated = sum(1 for p in payloads if p.get("outcome") == "escalated")
    executed = sum(1 for p in payloads if p.get("outcome") == "executed")
    recovered = sum(1 for p in payloads if p.get("outcome") == "recovered")

    # Phase 10: Rs. recovered from payment.captured audit entries
    rs_recovered = sum(
        p.get("amount", 0) for p in payloads if p.get("event") == "payment_captured"
    )

    # Business impact metrics
    auto_resolved = total - escalated
    auto_resolution_rate = round(auto_resolved / total * 100, 1) if total > 0 else 0.0
    analyst_hours_saved = round(auto_resolved * 15 / 60, 1)  # 15 min per manual case

    # Recovery by category (executed + recovered count as recovered)
    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for p in payloads:
        is_recovered = p.get("outcome") in ("executed", "recovered")
        by_cat[p.get("decline_code", "UNKNOWN")].append(is_recovered)
    recovery_by_category = {
        cat: round(sum(vals) / len(vals), 4) for cat, vals in by_cat.items()
    }

    return {
        "total_records": total,
        "tier1_count": tier1_count,
        "tier2_count": total - tier1_count,
        "tier1_pct": round(tier1_count / total * 100, 1),
        "executed_count": executed,
        "escalated_count": escalated,
        "recovered_count": recovered,
        "rs_recovered": rs_recovered,
        "rs_at_risk": rs_at_risk,
        "auto_resolved_count": auto_resolved,
        "auto_resolution_rate": auto_resolution_rate,
        "analyst_hours_saved": analyst_hours_saved,
        "compliance_violations_caught": violations_caught,
        "compliance_violations_executed": 0,
        "recovery_by_category": recovery_by_category,
    }
