# api/routes/human_review.py
from fastapi import APIRouter
from sqlalchemy import select
from models.db import AsyncSessionLocal, HumanReviewQueueORM

router = APIRouter()


@router.get("/human-review")
async def get_human_review():
    """Return all unresolved items in the human review queue."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(HumanReviewQueueORM)
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
async def resolve_human_review(review_id: str):
    """Mark a human review queue item as resolved."""
    from datetime import datetime, timezone
    from fastapi import HTTPException

    async with AsyncSessionLocal() as db:
        stmt = select(HumanReviewQueueORM).where(HumanReviewQueueORM.review_id == review_id)
        item = (await db.execute(stmt)).scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Review item '{review_id}' not found.")

        item.resolved_at = datetime.now(timezone.utc)
        await db.commit()

    return {"status": "resolved", "review_id": review_id, "resolved_at": item.resolved_at.isoformat()}
