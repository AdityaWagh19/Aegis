# scripts/make_live_demo_batch.py
"""
Generate a realistic 100-mandate enterprise demo batch CSV.
Embeds real Razorpay subscription IDs for the live recovery demo moment.

Usage:
    python scripts/make_live_demo_batch.py --subscriptions sub_XXX [sub_YYY ...]
"""
import argparse
import csv
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Realistic Indian customer names for authentic presentation
_INDIAN_NAMES = [
    "Aarav Sharma", "Rohan Mehta", "Priya Patel", "Vikram Malhotra", "Ananya Iyer",
    "Aditi Deshmukh", "Rahul Verma", "Sneha Kulkarni", "Amitabh Joshi", "Pooja Nair",
    "Kavita Rao", "Rajesh Gupta", "Sunil Singhania", "Deepika Reddy", "Neha Agarwal",
    "Manish Tiwari", "Divya Menon", "Siddharth Saxena", "Tarun Bhatia", "Ritu Chauhan",
    "Karan Kapoor", "Shreya Sen", "Arjun Nambiar", "Ishaan Chatterjee", "Meera Pillai",
    "Sanjay Varma", "Preeti Das", "Vivek Hegde", "Swati Bansal", "Abhishek Dubey",
    "Gaurav Pandey", "Ankita Roy", "Harish Natarajan", "Naveen Choudhury", "Pankaj Shukla",
    "Rituja Patil", "Varun Sethi", "Nidhi Kaushik", "Kunal Goswami", "Bhavna Mishra",
    "Saurabh Trivedi", "Tanvi Sengupta", "Alok Srivastava", "Smriti Mukhopadhyay", "Devendra Solanki",
    "Rachna Aggarwal", "Hemant Chauhan", "Geeta Somani", "Lalit Bohra", "Archana Prasad",
    "Yashwant Shenoy", "Pallavi Nadkarni", "Pranav Vasisht", "Sheetal Gokhale", "Rupesh Sawant",
    "Chirag Thakkar", "Dimple Parekh", "Mayank Soni", "Urvashi Bhatt", "Jatin Khatri",
    "Bhavesh Chawla", "Kamini Mahajan", "Tushar Rane", "Leena D'Souza", "Girish Prabhu",
    "Sadhana Kamath", "Pradeep Naik", "Mohan Lal", "Kailash Chand", "Kishore Kumar",
    "Lata Mangesh", "Hemlata Shah", "Gita Rathi", "Rashmi Jain", "Shalini Bhargava",
    "Anil Kapoor", "Vijay Deverakonda", "Dhanush Raj", "Mammootty Varghese", "Suriya Sivakumar",
    "Kalyani Priyadarshan", "Trisha Krishnan", "Samantha Prabhu", "Nayanthara Kurian", "Keerthy Suresh",
    "Rashmika Mandanna", "Sai Pallavi", "Dulquer Salmaan", "Fahadh Faasil", "Prithviraj Sukumaran",
    "Karthik Aryan", "Ayushmann Khurrana", "Rajkummar Rao", "Vicky Kaushal", "Pankaj Tripathi"
]


def main(subscription_ids: list[str], output: str):
    now = datetime.now(timezone.utc).isoformat()
    batch_id = str(uuid.uuid4())
    fieldnames = [
        "mandate_id", "customer_id", "amount", "mandate_type", "product_category",
        "decline_code", "days_since_salary_credit", "prior_bounce_count",
        "is_revocable", "attempt_number", "timestamp", "batch_id", "is_held_out", "correct_action"
    ]

    primary_sub = subscription_ids[0] if subscription_ids else "sub_live_demo"
    rows = []

    # -------------------------------------------------------------------------
    # 1. THE LIVE DEMO RECORD (Index 0):
    # Triggers SEND_UPI_INTENT_PUSH -> sends real email to presenter phone!
    # -------------------------------------------------------------------------
    rows.append({
        "mandate_id": primary_sub,
        "customer_id": "CUST-LIVE-001",
        "amount": 18000,
        "mandate_type": "UPI_AUTOPAY",
        "product_category": "subscription",
        "decline_code": "AFA_REQUIRED",
        "days_since_salary_credit": 5,
        "prior_bounce_count": 0,
        "is_revocable": "true",
        "attempt_number": "1",
        "timestamp": now,
        "batch_id": batch_id,
        "is_held_out": "False",
        "correct_action": "SEND_UPI_INTENT_PUSH",
    })

    # -------------------------------------------------------------------------
    # 2. NON-REVOCABLE HARD DECLINES (5 records):
    # Demonstrates Compliance Gate catching illegal retries -> human review
    # -------------------------------------------------------------------------
    for i in range(5):
        cust_id = f"CUST-NR-{i+1:03d}"
        amount = random.choice([25000, 35000, 48000, 60000, 75000])
        rows.append({
            "mandate_id": f"MAND-NR-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": cust_id,
            "amount": amount,
            "mandate_type": "ENACH",
            "product_category": "loan_emi",
            "decline_code": "NON_REVOCABLE_HARD_DECLINE",
            "days_since_salary_credit": random.choice([1, 2, 3]),
            "prior_bounce_count": random.choice([1, 2, 3]),
            "is_revocable": "false",  # Crucial: non-revocable
            "attempt_number": "2",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "ESCALATE_TO_HUMAN",
        })

    # -------------------------------------------------------------------------
    # 3. BANK TECHNICAL DECLINE (35 records):
    # Morning bank server downtime (SBI / HDFC) -> silent backoff retry
    # -------------------------------------------------------------------------
    for i in range(35):
        cust_id = f"CUST-BTD-{i+1:03d}"
        amount = random.choice([499, 999, 1499, 2999, 4500, 7500, 12000])
        mandate_type = random.choice(["UPI_AUTOPAY", "UPI_AUTOPAY", "ENACH"])
        category = random.choice(["subscription", "loan_emi", "sip", "insurance"])
        rows.append({
            "mandate_id": f"MAND-BTD-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": cust_id,
            "amount": amount,
            "mandate_type": mandate_type,
            "product_category": category,
            "decline_code": "BANK_TECHNICAL_DECLINE",
            "days_since_salary_credit": random.randint(3, 20),
            "prior_bounce_count": random.choice([0, 0, 1]),
            "is_revocable": "true",
            "attempt_number": "1",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "RETRY_AFTER_BACKOFF",
        })

    # -------------------------------------------------------------------------
    # 4. INSUFFICIENT FUNDS (30 records):
    # Pre-salary shortfall -> rescheduled to post-salary date
    # -------------------------------------------------------------------------
    for i in range(30):
        cust_id = f"CUST-NSF-{i+1:03d}"
        amount = random.choice([1200, 2500, 3800, 5000, 8500, 14000])
        days_since = random.choice([1, 2, 3, 28, 29, 30])  # Near salary boundary
        rows.append({
            "mandate_id": f"MAND-NSF-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": cust_id,
            "amount": amount,
            "mandate_type": random.choice(["UPI_AUTOPAY", "ENACH"]),
            "product_category": random.choice(["loan_emi", "loan_emi", "sip"]),
            "decline_code": "INSUFFICIENT_FUNDS",
            "days_since_salary_credit": days_since,
            "prior_bounce_count": random.choice([0, 1]),
            "is_revocable": "true",
            "attempt_number": "1",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "SCHEDULE_POST_SALARY",
        })

    # -------------------------------------------------------------------------
    # 5. AFA REQUIRED (14 synthetic records > 15,000 threshold):
    # Generates UPI Intent Push links
    # -------------------------------------------------------------------------
    for i in range(14):
        cust_id = f"CUST-AFA-{i+1:03d}"
        amount = random.choice([16500, 18500, 21000, 24000, 30000])
        rows.append({
            "mandate_id": f"MAND-AFA-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": cust_id,
            "amount": amount,
            "mandate_type": "UPI_AUTOPAY",
            "product_category": random.choice(["subscription", "sip", "insurance"]),
            "decline_code": "AFA_REQUIRED",
            "days_since_salary_credit": random.randint(5, 15),
            "prior_bounce_count": 0,
            "is_revocable": "true",
            "attempt_number": "1",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "SEND_UPI_INTENT_PUSH",
        })

    # -------------------------------------------------------------------------
    # 6. MANDATE PAUSED (10 records):
    # Customer paused in UPI app -> WhatsApp Hinglish nudge
    # -------------------------------------------------------------------------
    for i in range(10):
        cust_id = f"CUST-PSD-{i+1:03d}"
        amount = random.choice([499, 799, 1299, 2499, 3999])
        rows.append({
            "mandate_id": f"MAND-PSD-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": cust_id,
            "amount": amount,
            "mandate_type": "UPI_AUTOPAY",
            "product_category": "subscription",
            "decline_code": "MANDATE_PAUSED",
            "days_since_salary_credit": random.randint(4, 18),
            "prior_bounce_count": 0,
            "is_revocable": "true",
            "attempt_number": "1",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "SEND_HINGLISH_NUDGE",
        })

    # -------------------------------------------------------------------------
    # 7. MANDATE EXPIRED (5 records):
    # 1-year mandate validity ended -> send renewal link
    # -------------------------------------------------------------------------
    for i in range(5):
        cust_id = f"CUST-EXP-{i+1:03d}"
        amount = random.choice([999, 1499, 2999, 4999])
        rows.append({
            "mandate_id": f"MAND-EXP-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": cust_id,
            "amount": amount,
            "mandate_type": "UPI_AUTOPAY",
            "product_category": "subscription",
            "decline_code": "MANDATE_EXPIRED",
            "days_since_salary_credit": random.randint(2, 10),
            "prior_bounce_count": 0,
            "is_revocable": "true",
            "attempt_number": "1",
            "timestamp": now,
            "batch_id": batch_id,
            "is_held_out": "False",
            "correct_action": "SEND_MANDATE_RENEWAL_LINK",
        })

    # Write the complete 100-row batch
    out_path = Path(output)
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    total_amount = sum(r["amount"] for r in rows)
    print(f"\n{'='*60}")
    print(f"ENTERPRISE DEMO BATCH GENERATED: {len(rows)} RECORDS")
    print(f"{'='*60}")
    print(f"Total Amount at Risk:       Rs. {total_amount:,.2f}")
    print(f"  Live Record (Presenter):  1 (Primary: {primary_sub})")
    print(f"  Bank Technical Decline:   35 (Silent Backoff Retry)")
    print(f"  Insufficient Funds:       30 (Post-Salary Rescheduling)")
    print(f"  AFA Required (> Rs. 15k): 15 (UPI Intent Push)")
    print(f"  Mandate Paused:           10 (WhatsApp Hinglish Nudge)")
    print(f"  Mandate Expired:          5  (Mandate Renewal Link)")
    print(f"  Non-Revocable Decline:    5  (Compliance Overrides -> Human Review)")
    print(f"\nSaved to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscriptions", nargs="+", default=[], help="Real Razorpay subscription IDs")
    parser.add_argument("--output", default="data/live_demo_batch.csv")
    args = parser.parse_args()
    main(args.subscriptions, args.output)
