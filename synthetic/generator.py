# synthetic/generator.py
"""
Generates synthetic UPI Autopay / e-NACH mandate failure events.
Run before writing ANY Tier-1 rules or compliance logic.
Usage: python -m synthetic.generator --count 500 --output data/synthetic.csv --held-out-pct 0.2
"""
import argparse
import csv
import json
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker

fake = Faker("en_IN")


# Ground-truth action lookup (defines what the CORRECT action is for evaluation)
GROUND_TRUTH = {
    "INSUFFICIENT_FUNDS":         "SCHEDULE_POST_SALARY",
    "AFA_REQUIRED":               "SEND_UPI_INTENT_PUSH",
    "MANDATE_PAUSED":             "SEND_HINGLISH_NUDGE",
    "BANK_TECHNICAL_DECLINE":     "RETRY_AFTER_BACKOFF",
    "NON_REVOCABLE_HARD_DECLINE": "ESCALATE_TO_HUMAN",
    "MANDATE_EXPIRED":            "SEND_MANDATE_RENEWAL_LINK",
}

# Distribution mirrors compliance_config.yaml synthetic_distribution
DISTRIBUTION = {
    "INSUFFICIENT_FUNDS": 0.40,
    "BANK_TECHNICAL_DECLINE": 0.20,
    "MANDATE_PAUSED": 0.15,
    "AFA_REQUIRED": 0.10,
    "MANDATE_EXPIRED": 0.10,
    "NON_REVOCABLE_HARD_DECLINE": 0.05,
}


def generate_event(batch_id: str) -> dict:
    decline_code = random.choices(
        list(DISTRIBUTION.keys()),
        weights=list(DISTRIBUTION.values()),
        k=1
    )[0]

    mandate_type = random.choice(["UPI_AUTOPAY", "ENACH"])
    amount = random.randint(500, 150_000)
    is_revocable = True if decline_code != "NON_REVOCABLE_HARD_DECLINE" else False
    product_category = (
        "loan_emi" if not is_revocable
        else random.choice(["subscription", "sip", "insurance", "subscription", "subscription"])
    )
    attempt_number = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1], k=1)[0]
    # Cap attempt_number at the mandate-type maximum
    max_attempts = 3 if mandate_type == "UPI_AUTOPAY" else 2
    attempt_number = min(attempt_number, max_attempts)

    return {
        "mandate_id": str(uuid.uuid4()),
        "customer_id": f"CUST-{random.randint(1000, 9999)}",
        "amount": amount,
        "mandate_type": mandate_type,
        "product_category": product_category,
        "decline_code": decline_code,
        "days_since_salary_credit": random.randint(0, 30),
        "prior_bounce_count": random.randint(0, 4),
        "is_revocable": is_revocable,
        "attempt_number": attempt_number,
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48))).isoformat(),
        "batch_id": batch_id,
        "is_held_out": False,
        "correct_action": GROUND_TRUTH[decline_code],
    }


def generate_batch(count: int, output_path: str, held_out_pct: float = 0.2, seed: int = 42):
    random.seed(seed)
    batch_id = str(uuid.uuid4())
    events = [generate_event(batch_id) for _ in range(count)]

    # Write full dataset
    fieldnames = list(events[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)

    print(f"Generated {count} events -> {output_path}")

    # Split held-out
    n_held_out = int(count * held_out_pct)
    random.shuffle(events)
    held_out = events[:n_held_out]
    for e in held_out:
        e["is_held_out"] = True

    held_out_path = output_path.replace(".csv", "_held_out.csv")
    with open(held_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(held_out)

    print(f"Held-out set: {n_held_out} events -> {held_out_path}")
    print("IMPORTANT: Commit data/synthetic_held_out.csv before writing any rules.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output", default="data/synthetic.csv")
    parser.add_argument("--held-out-pct", type=float, default=0.2)
    args = parser.parse_args()
    generate_batch(args.count, args.output, args.held_out_pct)
