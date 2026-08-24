# scripts/make_demo_batch.py
"""Create a demo-specific batch with at least one of each category plus deliberate violations."""
import csv
import uuid
from datetime import datetime, timezone

RECORDS = [
    # Category mix (rounds to ~70% Tier-1 resolvable)
    *[{"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 3, "prior_bounce_count": 0, "amount": 12000, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(18)],
    *[{"decline_code": "BANK_TECHNICAL_DECLINE", "days_since_salary_credit": 10, "prior_bounce_count": 0, "amount": 8500, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(10)],
    *[{"decline_code": "MANDATE_PAUSED", "days_since_salary_credit": 7, "prior_bounce_count": 0, "amount": 5000, "is_revocable": True, "attempt_number": 1, "mandate_type": "ENACH"} for _ in range(7)],
    *[{"decline_code": "AFA_REQUIRED", "days_since_salary_credit": 5, "prior_bounce_count": 0, "amount": 18000, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(5)],
    *[{"decline_code": "MANDATE_EXPIRED", "days_since_salary_credit": 12, "prior_bounce_count": 0, "amount": 7500, "is_revocable": True, "attempt_number": 1, "mandate_type": "ENACH"} for _ in range(5)],
    # Deliberately ambiguous -> Tier-2
    *[{"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 22, "prior_bounce_count": 2, "amount": 9000, "is_revocable": True, "attempt_number": 2, "mandate_type": "UPI_AUTOPAY"} for _ in range(5)],
    *[{"decline_code": "AFA_REQUIRED", "days_since_salary_credit": 5, "prior_bounce_count": 0, "amount": 14200, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"} for _ in range(2)],
    # THE COMPLIANCE OVERRIDE MOMENT — mandate MAND-053
    {"decline_code": "NON_REVOCABLE_HARD_DECLINE", "days_since_salary_credit": 1, "prior_bounce_count": 2, "amount": 45000, "is_revocable": False, "attempt_number": 2, "mandate_type": "ENACH"},
    # --- Deliberate violations appended (guarantee ComplianceOverrideCards) ---
    # Composite case: funds-timing suggests reschedule, but Rs. 20,000 exceeds the
    # Rs. 15,000 NPCI AFA limit -> Tier-1's SCHEDULE_POST_SALARY must be blocked.
    {"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 3, "prior_bounce_count": 0, "amount": 20000, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"},
    # Ambiguous late-cycle IF above AFA threshold -> Tier-2 proposal gets gated.
    {"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 22, "prior_bounce_count": 2, "amount": 18000, "is_revocable": True, "attempt_number": 2, "mandate_type": "UPI_AUTOPAY"},
    {"decline_code": "INSUFFICIENT_FUNDS", "days_since_salary_credit": 22, "prior_bounce_count": 0, "amount": 16000, "is_revocable": True, "attempt_number": 1, "mandate_type": "UPI_AUTOPAY"},
]

now = datetime.now(timezone.utc).isoformat()
fieldnames = ["mandate_id", "customer_id", "amount", "mandate_type", "product_category",
              "decline_code", "days_since_salary_credit", "prior_bounce_count",
              "is_revocable", "attempt_number", "timestamp", "batch_id", "is_held_out", "correct_action"]

batch_id = str(uuid.uuid4())
rows = []
for i, r in enumerate(RECORDS):
    rows.append({
        "mandate_id": f"MAND-{i+1:03d}",
        "customer_id": f"CUST-{1000+i}",
        "product_category": "loan_emi" if not r["is_revocable"] else "subscription",
        "timestamp": now,
        "batch_id": batch_id,
        "is_held_out": False,
        "correct_action": "",
        **r,
    })

with open("data/demo_batch.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f"Demo batch created: {len(rows)} records -> data/demo_batch.csv")
print("NON_REVOCABLE mandate ID: MAND-053 (the compliance override case)")
print("Deliberate-gate-catch mandates: MAND-054 (deterministic), MAND-055/MAND-056 (via Tier-2)")
