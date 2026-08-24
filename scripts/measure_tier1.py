# scripts/measure_tier1.py
# Run from repo root after Phase 1 synthetic data is generated
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.mandate_event import MandateEvent
from core.tier1_engine import classify
from datetime import datetime, timezone

with open("data/synthetic.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

events = []
for row in rows:
    row["timestamp"] = datetime.fromisoformat(row["timestamp"])
    row["is_revocable"] = row["is_revocable"].lower() == "true"
    row["is_held_out"] = row["is_held_out"].lower() == "true"
    row["amount"] = int(row["amount"])
    row["days_since_salary_credit"] = int(row["days_since_salary_credit"])
    row["prior_bounce_count"] = int(row["prior_bounce_count"])
    row["attempt_number"] = int(row["attempt_number"])
    events.append(MandateEvent(**row))

start = time.perf_counter()
results = [classify(e) for e in events]
elapsed_ms = (time.perf_counter() - start) * 1000

resolved = sum(1 for r in results if not r.is_ambiguous)
print(f"Total: {len(results)}")
print(f"Tier-1 resolved: {resolved} ({resolved/len(results)*100:.1f}%)")
print(f"Ambiguous (Tier-2): {len(results)-resolved} ({(len(results)-resolved)/len(results)*100:.1f}%)")
print(f"Total elapsed: {elapsed_ms:.1f}ms | P95 per record: {elapsed_ms*0.95/len(results):.2f}ms")
