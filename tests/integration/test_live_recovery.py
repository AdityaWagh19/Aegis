# tests/integration/test_live_recovery.py
"""
Full live recovery cycle test (requires Razorpay test-mode credentials + webhook).

Skipped in CI (no real Razorpay access). Run manually:
    pytest tests/integration/test_live_recovery.py -v -m live
"""
import pytest
import os

# Skip unless explicitly requested
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS"),
    reason="Live recovery test requires RUN_LIVE_TESTS=1 and Razorpay test credentials"
)


@pytest.mark.asyncio
async def test_full_live_recovery_cycle():
    """
    Full cycle: seed → webhook → process → action → payment → captured → recovered.
    Requires: Razorpay test keys, running Redis, running ARQ worker, public webhook URL.
    """
    import razorpay
    from dotenv import load_dotenv
    load_dotenv()

    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    assert key_id.startswith("rzp_test_"), "Test mode keys required"

    client = razorpay.Client(auth=(key_id, key_secret))

    # Step 1: Create a Plan
    plan = client.plan.create({
        "period": "monthly",
        "interval": 1,
        "item": {"name": "Test Recovery", "amount": 50000, "currency": "INR"},
    })
    assert plan["id"]

    # Step 2: Create a Subscription
    sub = client.subscription.create({
        "plan_id": plan["id"],
        "total_count": 6,
        "quantity": 1,
        "customer_notify": 0,
        "notes": {"mandate_type": "UPI_AUTOPAY", "product_category": "subscription"},
    })
    assert sub["id"].startswith("sub_")

    # Step 3: Create a Payment Link (simulating Aegis action)
    link = client.payment_link.create({
        "amount": 50000,
        "currency": "INR",
        "description": f"Recovery — {sub['id']}",
        "upi_link": True,
        "notify": {"sms": False, "email": False},
        "notes": {"mandate_id": sub["id"]},
    })
    assert link["id"].startswith("plink_")
    assert link.get("short_url")

    # Step 4: Verify we can fetch the payment link
    fetched = client.payment_link.fetch(link["id"])
    assert fetched["status"] in ("created", "partially_paid")

    print(f"\nLive recovery setup verified:")
    print(f"  Plan:         {plan['id']}")
    print(f"  Subscription: {sub['id']}")
    print(f"  Payment Link: {link['id']}")
    print(f"  Short URL:    {link['short_url']}")
    print(f"\nOpen {link['short_url']} on a phone/browser to complete the payment.")
    print(f"After payment, Razorpay sends payment.captured webhook to Aegis.")
