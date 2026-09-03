# api/routes/audit.py
from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, func
from models.db import AsyncSessionLocal, AuditLogORM
from models.tenant import TenantSchema
from api.middleware.auth import get_tenant_from_request

router = APIRouter()


@router.get("/audit")
async def get_audit(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    tenant: TenantSchema = Depends(get_tenant_from_request),
):
    """Paginated append-only audit log scoped to authenticated tenant."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AuditLogORM)
            .where(AuditLogORM.tenant_id == tenant.tenant_id)
            .order_by(AuditLogORM.entry_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        entries = (await db.execute(stmt)).scalars().all()
        total_stmt = (
            select(func.count(AuditLogORM.entry_id))
            .where(AuditLogORM.tenant_id == tenant.tenant_id)
        )
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

