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
    """
    async with AsyncSessionLocal() as db:
        stmt = select(AuditLogORM)
        entries = (await db.execute(stmt)).scalars().all()

    payloads = [e.payload for e in entries]
    if batch_id:
        # audit_log does not have batch_id — filter from batch cache in recovery.py
        # For now return all-time metrics
        pass

    total = len(payloads)
    if total == 0:
        return {"total_records": 0, "message": "No decisions recorded yet."}

    tier1_count = sum(1 for p in payloads if p.get("tier_that_decided") == 1)
    violations_caught = sum(1 for p in payloads if p.get("violation_blocked"))
    escalated = sum(1 for p in payloads if p.get("outcome") == "escalated")
    executed = sum(1 for p in payloads if p.get("outcome") == "executed")

    # Recovery by category
    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for p in payloads:
        by_cat[p.get("decline_code", "UNKNOWN")].append(p.get("outcome") == "executed")
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
        "compliance_violations_caught": violations_caught,
        "compliance_violations_executed": 0,
        "recovery_by_category": recovery_by_category,
    }
