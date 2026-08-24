# scripts/smoke_test_pipeline.py
"""
End-to-end pipeline smoke test (Phase 5).
Runs a small batch through process_batch(): Tier-1 -> Tier-2 (live Groq for
ambiguous cases) -> Compliance Gate -> Action Executor (real Razorpay TEST-MODE
APIs) -> Audit Log (SQLite). No mocks.

Expected outcomes per category:
  - Retry/schedule actions: Razorpay returns 404 for unknown subscription ids
    -> outcome="failed" (expected with synthetic mandate ids; proves error path)
  - Payment-link actions: REAL test-mode payment links are created in your
    Razorpay dashboard -> outcome="executed"
  - Nudge / monitor: outcome="mocked"
  - Non-revocable escalation: outcome="escalated" + human_review_queue row
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.mandate_event import MandateEvent
from core.orchestrator import process_batch

BASE = dict(
    mandate_type="UPI_AUTOPAY", product_category="subscription",
    days_since_salary_credit=5, prior_bounce_count=0,
    is_revocable=True, attempt_number=1, timestamp=datetime.now(timezone.utc),
)

EVENTS = [
    MandateEvent(**{**BASE, "customer_id": "SMOKE-A", "amount": 8000,
                    "decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 22}),   # ambiguous -> Tier-2
    MandateEvent(**{**BASE, "customer_id": "SMOKE-B", "amount": 14200,
                    "decline_code": "AFA_REQUIRED"}),                                          # borderline AFA -> Tier-2
    MandateEvent(**{**BASE, "customer_id": "SMOKE-C", "amount": 45000,
                    "decline_code": "NON_REVOCABLE_HARD_DECLINE", "is_revocable": False}),     # escalate
    MandateEvent(**{**BASE, "customer_id": "SMOKE-D", "amount": 5000,
                    "decline_code": "MANDATE_PAUSED"}),                                        # nudge
    MandateEvent(**{**BASE, "customer_id": "SMOKE-E", "amount": 6000,
                    "decline_code": "BANK_TECHNICAL_DECLINE", "attempt_number": 1}),           # retry
    MandateEvent(**{**BASE, "customer_id": "SMOKE-F", "amount": 7000,
                    "decline_code": "MANDATE_EXPIRED"}),                                       # renewal link
]


async def run():
    result = await process_batch(EVENTS)
    m = result.metrics
    print(f"\nBatch {result.batch_id} status={result.status}")
    print(f"  total={m.total_records} tier1={m.tier1_count} ({m.tier1_pct}%) tier2={m.tier2_count}")
    print(f"  rs_recovered={m.rs_recovered} rs_at_risk={m.rs_at_risk} recovery_rate={m.recovery_rate}")
    print(f"  violations_caught={m.compliance_violations_caught} violations_executed={m.compliance_violations_executed}")
    print("\nDecisions:")
    for d in result.decisions:
        print(f"  {d.mandate_id[:8]}... tier={d.tier_that_decided} proposed={d.proposed_action:26s} "
              f"final={d.final_action:24s} outcome={d.outcome}")
        if d.hinglish_message:
            print(f"      Hinglish: {d.hinglish_message[:90]}")


asyncio.run(run())
