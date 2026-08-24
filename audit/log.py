# audit/log.py
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from models.db import AuditLogORM
from models.mandate_event import MandateEvent
from models.recovery_decision import RecoveryDecision

logger = logging.getLogger(__name__)


class AuditLog:
    """
    Append-only audit log.
    Exposes only append(). No update() or delete() methods exist.
    """

    async def append(
        self,
        event: MandateEvent,
        decision: RecoveryDecision,
        db: AsyncSession,
    ) -> None:
        payload = {
            "mandate_id": event.mandate_id,
            "customer_id": event.customer_id,
            "amount": event.amount,
            "mandate_type": event.mandate_type,
            "decline_code": event.decline_code,
            "tier_that_decided": decision.tier_that_decided,
            "proposed_action": decision.proposed_action,
            "compliance_approved": decision.compliance_result.approved,
            "violation_blocked": decision.compliance_result.violation_blocked,
            "violation_rule": decision.compliance_result.violation_rule,
            "final_action": decision.final_action,
            "outcome": decision.outcome,
            "rationale": decision.rationale,
            "confidence": decision.confidence,
            "hinglish_message_preview": (
                decision.hinglish_message[:100] if decision.hinglish_message else None
            ),
            "alternatives_considered": decision.alternatives_considered,
        }
        entry = AuditLogORM(
            mandate_id=event.mandate_id,
            decision_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            payload=payload,
        )
        db.add(entry)
        await db.commit()
        # NOTE (Phase 9 migration): This commits once per mandate event (one round-trip per record).
        # For PostgreSQL at production scale, remove this per-record commit and instead batch-commit
        # all AuditLog entries at the end of process_batch() for a single round-trip per batch.
        logger.debug("Audit entry written for mandate_id=%s", event.mandate_id)


# Module-level singleton
audit_log = AuditLog()
