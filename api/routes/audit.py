# api/routes/audit.py
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from models.db import AsyncSessionLocal, AuditLogORM

router = APIRouter()


@router.get("/audit")
async def get_audit(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, le=200)):
    """Paginated append-only audit log."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AuditLogORM)
            .order_by(AuditLogORM.entry_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        entries = (await db.execute(stmt)).scalars().all()
        total_stmt = select(func.count(AuditLogORM.entry_id))  # func.count, not func().count
        total = (await db.execute(total_stmt)).scalar_one()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "entry_id": e.entry_id,
                "mandate_id": e.mandate_id,
                "timestamp": e.timestamp.isoformat(),
                **e.payload,
            }
            for e in entries
        ],
    }
