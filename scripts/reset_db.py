# scripts/reset_db.py
"""
Reset transaction and batch tables to start clean at 0 records for demo.
Preserves tenant configurations while clearing:
- Recovery decisions
- Mandate events
- Audit logs
- Batch jobs

Works on both SQLite and PostgreSQL.
Usage:
    python scripts/reset_db.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import delete
from models.db import (
    AsyncSessionLocal, init_db,
    RecoveryDecisionORM, MandateEventORM, AuditLogORM, BatchJobORM
)


async def reset():
    await init_db()
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import text
            await db.execute(text("TRUNCATE TABLE audit_log, recovery_decisions, mandate_events, batch_jobs CASCADE"))
            await db.commit()
        except Exception:
            await db.rollback()
            await db.execute(delete(AuditLogORM))
            await db.execute(delete(RecoveryDecisionORM))
            await db.execute(delete(MandateEventORM))
            await db.execute(delete(BatchJobORM))
            await db.commit()
    print("Database reset successfully: All mandate events, decisions, and audit logs cleared.")
    print("Metrics endpoint now returns total_records=0, rs_recovered=0.")


if __name__ == "__main__":
    asyncio.run(reset())
