# synthetic/evaluator.py
"""
Held-out evaluation. Full implementation completed in Phase 8.
The function signature and return type are defined here so Phase 2+
can reference the expected metrics structure.
"""
import csv
from models.recovery_decision import EvaluationResult


def load_held_out_events(path: str = "data/synthetic_held_out.csv") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate_held_out_set() -> EvaluationResult:
    """
    Runs the full pipeline on the held-out set and returns evaluation metrics.
    Full implementation in Phase 8 after process_batch() is available.
    """
    raise NotImplementedError("Implemented in Phase 8 after process_batch() is complete.")
