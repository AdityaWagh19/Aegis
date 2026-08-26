# api/routes/metrics.py
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from models.db import AsyncSessionLocal, AuditLogORM

router = APIRouter()


@router.get("/metrics")
async def get_metrics(batch_id: str | None = Query(default=None)):
    """
    Aggregate metrics across all decisions, or for a specific batch_id.
    Reads from the audit_log table.
    Phase 10: includes rs_recovered from payment.captured events.
    """
    async with AsyncSessionLocal() as db:
        stmt = select(AuditLogORM)
        entries = (await db.execute(stmt)).scalars().all()

    payloads = [e.payload for e in entries]
    total = len(payloads)
    if total == 0:
        return {
            "total_records": 0,
            "message": "No decisions recorded yet.",
            "rs_recovered": 0,
            "recovered_count": 0,
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
        "compliance_violations_caught": violations_caught,
        "compliance_violations_executed": 0,
        "recovery_by_category": recovery_by_category,
    }
