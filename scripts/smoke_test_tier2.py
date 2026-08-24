# scripts/smoke_test_tier2.py
"""Run manually to verify Groq connectivity and response quality."""
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.mandate_event import MandateEvent
from core.tier2_agent import tier2_reason

TEST_CASES = [
    dict(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=20, prior_bounce_count=2, amount=8000),
    dict(decline_code="AFA_REQUIRED", amount=14200, mandate_type="UPI_AUTOPAY"),
    dict(decline_code="NON_REVOCABLE_HARD_DECLINE", is_revocable=False, amount=45000),
]

latencies_ms = []


async def run():
    # Base defaults merged with per-case overrides (plan bugfix: avoids
    # duplicate-kwarg TypeError when a test case overrides a base field).
    base = dict(
        customer_id="SMOKE-001", mandate_type="UPI_AUTOPAY",
        product_category="subscription", days_since_salary_credit=5,
        prior_bounce_count=0, is_revocable=True, attempt_number=1,
        timestamp=datetime.now(timezone.utc),
    )
    for case in TEST_CASES:
        event = MandateEvent(**{**base, **case})
        start = time.perf_counter()
        result = await tier2_reason(event)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed_ms)
        print(f"\n--- {event.decline_code} ---")
        print(f"Action:     {result.action}")
        print(f"Confidence: {result.confidence}")
        print(f"Hinglish:   {result.message_hinglish}")
        print(f"Rationale:  {result.rationale}")
        print(f"Latency:    {elapsed_ms:.0f}ms")


asyncio.run(run())

avg = sum(latencies_ms) / len(latencies_ms)
print(f"\nAverage latency: {avg:.0f}ms across {len(latencies_ms)} calls (target < 3000ms)")
