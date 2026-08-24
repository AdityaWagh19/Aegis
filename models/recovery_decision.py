# models/recovery_decision.py
from typing import Literal, Optional
from pydantic import BaseModel


class ComplianceResult(BaseModel):
    approved: bool
    final_action: str
    violation_blocked: bool
    violation_rule: Optional[str] = None


class Tier1Result(BaseModel):
    action: Optional[str] = None   # None when is_ambiguous=True — case routes to Tier-2
    is_ambiguous: bool
    reason: str
    tier: Literal[1] = 1


class Tier2Result(BaseModel):
    action: Literal[
        "RETRY_AFTER_BACKOFF",
        "SCHEDULE_POST_SALARY",
        "SEND_UPI_INTENT_PUSH",
        "SEND_MANDATE_RENEWAL_LINK",
        "SEND_HINGLISH_NUDGE",
        "ESCALATE_TO_HUMAN",
        "NO_ACTION_MONITORING",
    ]
    message_hinglish: str
    rationale: str
    confidence: float          # 0.0 – 1.0
    alternatives_considered: Optional[list[str]] = None
    tier: Literal[2] = 2


class RecoveryDecision(BaseModel):
    mandate_id: str
    tier_that_decided: int               # 1 or 2
    proposed_action: str
    compliance_result: ComplianceResult
    final_action: str
    outcome: str                         # "executed" | "mocked" | "escalated" | "failed"
    rationale: Optional[str] = None
    confidence: Optional[float] = None
    hinglish_message: Optional[str] = None
    alternatives_considered: Optional[list[str]] = None
    razorpay_response: Optional[dict] = None


class BatchMetrics(BaseModel):
    total_records: int
    tier1_count: int
    tier2_count: int
    tier1_pct: float
    recovery_rate: float
    rs_recovered: int
    rs_at_risk: int
    compliance_violations_caught: int
    compliance_violations_executed: int
    false_escalation_rate: Optional[float] = None


class BatchResult(BaseModel):
    batch_id: str
    status: str
    metrics: BatchMetrics
    decisions: list[RecoveryDecision]


class EvaluationResult(BaseModel):
    total_held_out: int
    correct_actions: int
    accuracy: float
    recovery_rate_by_category: dict[str, float]
    false_escalation_rate: float
    tier1_resolution_rate: float
    tier2_resolution_rate: float
    compliance_violations_caught: int
    compliance_violations_executed: int   # Must be 0
