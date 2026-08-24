# api/routes/mandates.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from models.db import AsyncSessionLocal, AuditLogORM

router = APIRouter()


@router.get("/mandates/{mandate_id}")
async def get_mandate(mandate_id: str):
    """Return the full audit log entry for a single mandate."""
    async with AsyncSessionLocal() as db:
        stmt = select(AuditLogORM).where(AuditLogORM.mandate_id == mandate_id)
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
