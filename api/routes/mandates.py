# api/routes/mandates.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from models.db import AsyncSessionLocal, AuditLogORM
from models.tenant import TenantSchema
from api.middleware.auth import get_tenant_from_request

router = APIRouter()


@router.get("/mandates/{mandate_id}")
async def get_mandate(
    mandate_id: str,
    tenant: TenantSchema = Depends(get_tenant_from_request),
):
    """Return the full audit log entry for a single mandate within the calling tenant."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AuditLogORM)
            .where(AuditLogORM.mandate_id == mandate_id)
            .where(AuditLogORM.tenant_id == tenant.tenant_id)
        )
        result = await db.execute(stmt)
        entry = result.scalars().first()
        if not entry:
            raise HTTPException(status_code=404, detail=f"Mandate '{mandate_id}' not found in audit log.")
        return {
            "entry_id": entry.entry_id,
            "mandate_id": entry.mandate_id,
            "timestamp": entry.timestamp.isoformat(),
            "payload": entry.payload,
        }

