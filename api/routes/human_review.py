# api/routes/human_review.py
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from models.db import AsyncSessionLocal, HumanReviewQueueORM
from models.tenant import TenantSchema
from api.middleware.auth import get_tenant_from_request

router = APIRouter()


@router.get("/human-review")
async def get_human_review(tenant: TenantSchema = Depends(get_tenant_from_request)):
    """Return all unresolved items in the human review queue for the calling tenant."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(HumanReviewQueueORM)
            .where(HumanReviewQueueORM.tenant_id == tenant.tenant_id)
            .where(HumanReviewQueueORM.resolved_at == None)
            .order_by(HumanReviewQueueORM.created_at.asc())
        )
        items = (await db.execute(stmt)).scalars().all()

    return {
        "total": len(items),
        "items": [
            {
                "review_id": item.review_id,
                "mandate_id": item.mandate_id,
                "reason": item.reason,
                "compliance_rule": item.compliance_rule,
                "created_at": item.created_at.isoformat(),
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            }
            for item in items
        ],
    }


@router.post("/human-review/{review_id}/resolve")
async def resolve_human_review(
    review_id: str,
    tenant: TenantSchema = Depends(get_tenant_from_request),
):
    """Mark a human review queue item as resolved within the calling tenant."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(HumanReviewQueueORM)
            .where(HumanReviewQueueORM.review_id == review_id)
            .where(HumanReviewQueueORM.tenant_id == tenant.tenant_id)
        )
        item = (await db.execute(stmt)).scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Review item '{review_id}' not found.")

        item.resolved_at = datetime.now(timezone.utc)
        item.resolved_by = tenant.name
        await db.commit()

    return {"status": "resolved", "review_id": review_id, "resolved_at": item.resolved_at.isoformat()}

