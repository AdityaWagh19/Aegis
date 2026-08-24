# synthetic/evaluator.py
"""
Held-out evaluation.
Runs the full pipeline on the held-out set and reports metrics.
CRITICAL: Call this before recording the demo. Assert compliance_violations_executed == 0.
"""
import asyncio
import csv
import json
from datetime import datetime, timezone

from models.mandate_event import MandateEvent
from models.recovery_decision import EvaluationResult
from core.orchestrator import process_batch


def load_held_out_events(path: str = "data/synthetic_held_out.csv") -> list[MandateEvent]:
    events = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
            row["is_revocable"] = row["is_revocable"].lower() == "true"
            row["is_held_out"] = row["is_held_out"].lower() == "true"
            row["amount"] = int(row["amount"])
            row["days_since_salary_credit"] = int(row["days_since_salary_credit"])
            row["prior_bounce_count"] = int(row["prior_bounce_count"])
            row["attempt_number"] = int(row["attempt_number"])
            events.append(MandateEvent(**row))
    return events


async def _run_evaluation(events: list[MandateEvent]) -> EvaluationResult:
    batch_result = await process_batch(events)

    correct = sum(
        1
        for decision, event in zip(batch_result.decisions, events)
        if event.correct_action and decision.final_action == event.correct_action
    )

    # Per-category accuracy
    from collections import defaultdict
    cat_correct: dict[str, list[bool]] = defaultdict(list)
    for decision, event in zip(batch_result.decisions, events):
        if event.correct_action:
            cat_correct[event.decline_code].append(decision.final_action == event.correct_action)

    recovery_by_category = {
        cat: round(sum(vals) / len(vals), 4)
        for cat, vals in cat_correct.items()
    }

    # False escalation: escalated but correct_action was not ESCALATE_TO_HUMAN
    false_escalations = sum(
        1
        for decision, event in zip(batch_result.decisions, events)
        if decision.final_action == "ESCALATE_TO_HUMAN"
        and event.correct_action != "ESCALATE_TO_HUMAN"
    )
    false_escalation_rate = false_escalations / len(events) if events else 0.0

    return EvaluationResult(
        total_held_out=len(events),
        correct_actions=correct,
        accuracy=round(correct / len(events), 4) if events else 0.0,
        recovery_rate_by_category=recovery_by_category,
        false_escalation_rate=round(false_escalation_rate, 4),
        tier1_resolution_rate=round(batch_result.metrics.tier1_pct / 100, 4),
        tier2_resolution_rate=round(batch_result.metrics.tier2_count / len(events), 4) if events else 0.0,
        compliance_violations_caught=batch_result.metrics.compliance_violations_caught,
        compliance_violations_executed=batch_result.metrics.compliance_violations_executed,
    )


def evaluate_held_out_set(path: str = "data/synthetic_held_out.csv") -> EvaluationResult:
    """
    Load the held-out set and run the full pipeline evaluation.

    IMPORTANT: Do NOT call this function from inside an async context (e.g., an
    asyncio test, a pytest-asyncio test, or a Jupyter notebook with an active
    event loop). `asyncio.run()` will raise `RuntimeError: This event loop is
    already running` in those environments.

    Correct usage: `python -m synthetic.evaluator` from the terminal.
    """
    events = load_held_out_events(path)
    result = asyncio.run(_run_evaluation(events))

    # Print report
    print("\n" + "=" * 60)
    print("AEGIS HELD-OUT EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total held-out records:     {result.total_held_out}")
    print(f"Correct actions:            {result.correct_actions}")
    print(f"Overall accuracy:           {result.accuracy:.1%}")
    print(f"Tier-1 resolution rate:     {result.tier1_resolution_rate:.1%}")
    print(f"Tier-2 resolution rate:     {result.tier2_resolution_rate:.1%}")
    print(f"False escalation rate:      {result.false_escalation_rate:.1%}")
    print(f"Compliance violations caught:   {result.compliance_violations_caught}")
    print(f"Compliance violations executed: {result.compliance_violations_executed}")
    print("\nRecovery rate by category:")
    for cat, rate in sorted(result.recovery_rate_by_category.items()):
        print(f"  {cat:<35} {rate:.1%}")
    print("=" * 60)

    # HARD ASSERTION — do not record demo if this fails
    assert result.compliance_violations_executed == 0, (
        f"\nCRITICAL: {result.compliance_violations_executed} compliance violation(s) reached execution.\n"
        "Do not record the demo until this is resolved.\n"
        "Check compliance_gate.py and action_executor.py."
    )
    print("\nAssertion passed: compliance_violations_executed == 0")
    print("Safe to proceed to demo recording.\n")

    # Write results to file for submission reference
    with open("evaluation_results.json", "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    print("Results written to evaluation_results.json")

    return result


if __name__ == "__main__":
    evaluate_held_out_set()
