# scripts/make_live_demo_batch.py
"""
Generate a demo CSV using REAL Razorpay subscription IDs (from seed_razorpay.py output).

Usage:
    python scripts/make_live_demo_batch.py --subscriptions sub_XXX sub_YYY sub_ZZZ
"""
import argparse
import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main(subscription_ids: list[str], output: str):
    now = datetime.now(timezone.utc).isoformat()
    batch_id = str(uuid.uuid4())
    fieldnames = [
        "mandate_id", "customer_id", "amount", "mandate_type", "product_category",
        "decline_code", "days_since_salary_credit", "prior_bounce_count",
        "is_revocable", "attempt_number", "timestamp", "batch_id", "is_held_out", "correct_action"
    ]

    rows = []
    for i, sub_id in enumerate(subscription_ids):
        if i == len(subscription_ids) - 1:
            # Last subscription = the AFA_REQUIRED case (amount > Rs. 15,000 → triggers UPI intent push)
            row = {
                "decline_code": "AFA_REQUIRED",
                "amount": 18000,
                "days_since_salary_credit": 5,
                "prior_bounce_count": 0,
                "is_revocable": "true",
                "attempt_number": "1",
                "mandate_type": "UPI_AUTOPAY",
                "product_category": "subscription",
            }
        elif i == len(subscription_ids) - 2 and len(subscription_ids) >= 3:
            # Second-to-last = non-revocable (triggers escalation — the demo moment)
            row = {
                "decline_code": "NON_REVOCABLE_HARD_DECLINE",
                "amount": 45000,
                "days_since_salary_credit": 1,
                "prior_bounce_count": 2,
                "is_revocable": "false",
                "attempt_number": "2",
                "mandate_type": "ENACH",
                "product_category": "loan_emi",
            }
        else:
            # Most subscriptions = BANK_TECHNICAL_DECLINE (safe to retry)
            row = {
                "decline_code": "BANK_TECHNICAL_DECLINE",
                "amount": 5000,
                "days_since_salary_credit": 5,
                "prior_bounce_count": 0,
                "is_revocable": "true",
                "attempt_number": "1",
                "mandate_type": "UPI_AUTOPAY",
                "product_category": "subscription",
            }

        rows.append({
            "mandate_id": sub_id,
            "customer_id": f"CUST-LIVE-{i+1:03d}",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "",
            **row,
        })

    out_path = Path(output)
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Live demo batch created: {len(rows)} records -> {output}")
    print(f"  BTD (retry):     {sum(1 for r in rows if r['decline_code'] == 'BANK_TECHNICAL_DECLINE')}")
    print(f"  NON_REVOCABLE:   {sum(1 for r in rows if r['decline_code'] == 'NON_REVOCABLE_HARD_DECLINE')}")
    print(f"  AFA_REQUIRED:    {sum(1 for r in rows if r['decline_code'] == 'AFA_REQUIRED')}")
    print(f"\nUpload via dashboard or:")
    print(f'  curl -X POST https://aegis-platform.duckdns.org/api/v1/recovery/batch -F "file=@{output}"')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscriptions", nargs="+", required=True, help="Real Razorpay subscription IDs")
    parser.add_argument("--output", default="data/live_demo_batch.csv")
    args = parser.parse_args()
    main(args.subscriptions, args.output)
