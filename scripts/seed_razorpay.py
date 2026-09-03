# scripts/seed_razorpay.py
"""
Seed Razorpay test mode with real Plans + Subscriptions for the live demo.

Usage:
    python scripts/seed_razorpay.py --count 5

Creates:
    1. A Plan (monthly recurring, Rs. 500/month)
    2. N Subscriptions on that plan
    3. Prints the subscription IDs for use in make_live_demo_batch.py

Requires RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env (test mode keys).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv
load_dotenv()

import razorpay


def main(count: int):
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_id.startswith("rzp_test_"):
        print("ERROR: RAZORPAY_KEY_ID must be a test-mode key (rzp_test_*)")
        sys.exit(1)

    client = razorpay.Client(auth=(key_id, key_secret))

    # Step 1: Create a Plan (monthly recurring Rs. 500)
    print("Creating Plan...")
    plan = client.plan.create({
        "period": "monthly",
        "interval": 1,
        "item": {
            "name": "Aegis Demo Subscription",
            "amount": 50000,  # Paise = Rs. 500
            "currency": "INR",
            "description": "Monthly subscription for Aegis live recovery demo"
        },
        "notes": {"purpose": "aegis_live_demo"}
    })
    plan_id = plan["id"]
    print(f"  Plan ID: {plan_id}")

    # Step 2: Create N Subscriptions
    print(f"\nCreating {count} Subscriptions...")
    subscriptions = []
    for i in range(count):
        try:
            sub = client.subscription.create({
                "plan_id": plan_id,
                "total_count": 12,  # 12 monthly cycles
                "quantity": 1,
                "customer_notify": 0,  # We'll notify via Aegis
                "notes": {
                    "mandate_type": "UPI_AUTOPAY",
                    "product_category": "subscription",
                    "days_since_salary_credit": 5,
                    "prior_bounce_count": 0,
                    "is_revocable": "true",
                    "attempt_number": "1",
                    "demo_index": str(i),
                }
            })
            subscriptions.append({
                "subscription_id": sub["id"],
                "status": sub["status"],
                "short_url": sub.get("short_url", "N/A"),
            })
            print(f"  [{i+1}/{count}] {sub['id']} — status: {sub['status']}")
            time.sleep(0.5)  # Rate limit courtesy
        except Exception as e:
            print(f"  [{i+1}/{count}] ERROR: {e}")

    # Step 3: Print summary for CSV generation
    print(f"\n{'='*60}")
    print("SUBSCRIPTION IDs (use with make_live_demo_batch.py)")
    print(f"{'='*60}")
    for s in subscriptions:
        print(f"  {s['subscription_id']}  status={s['status']}")
    print(f"\nExample usage:")
    ids = " ".join(s["subscription_id"] for s in subscriptions)
    print(f"  python scripts/make_live_demo_batch.py --subscriptions {ids}")
    print(f"\nPlan ID for cleanup: {plan_id}")


import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()
    main(args.count)
