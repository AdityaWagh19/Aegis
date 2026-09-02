# core/tier1_engine.py
"""
Tier-1: Deterministic mandate failure rule engine.
INVARIANT: This file must never import from core.tier2_agent, groq, or any LLM SDK.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from core.config import load_config
from models.mandate_event import MandateEvent, ALLOWED_ACTIONS
from models.recovery_decision import Tier1Result

if TYPE_CHECKING:
    from core.config import ComplianceConfig

_cfg = load_config()
_MAX_RETRIES = _cfg.max_retry_attempts
_AFA_GENERAL = _cfg.afa_threshold_general
_AFA_SIP = _cfg.afa_threshold_sip_insurance
_BORDERLINE_PCT = 0.10   # Within 10% below threshold = ambiguous


def _get_afa_threshold(event: MandateEvent, config: ComplianceConfig | None = None) -> int:
    if config:
        afa_sip = config.afa_threshold_sip_insurance
        afa_general = config.afa_threshold_general
    else:
        afa_sip = _AFA_SIP
        afa_general = _AFA_GENERAL
    if event.product_category in ("sip", "insurance"):
        return afa_sip
    return afa_general


def _max_attempts(event: MandateEvent, config: ComplianceConfig | None = None) -> int:
    if config:
        max_upi = config.max_retry_attempts.UPI_AUTOPAY
        max_enach = config.max_retry_attempts.ENACH
    else:
        max_upi = _MAX_RETRIES.UPI_AUTOPAY
        max_enach = _MAX_RETRIES.ENACH
    return max_upi if event.mandate_type == "UPI_AUTOPAY" else max_enach


def classify(event: MandateEvent, config: ComplianceConfig | None = None) -> Tier1Result:
    """
    Classify a mandate failure event and return a deterministic action.
    Returns is_ambiguous=True when the case requires LLM reasoning.

    When config is provided (Phase 9 multi-tenancy), uses per-tenant thresholds.
    Otherwise falls back to module-level defaults from compliance_config.yaml.
    """
    code = event.decline_code

    # --- INSUFFICIENT_FUNDS ---
    if code == "INSUFFICIENT_FUNDS":
        # Contextual override order: (1) high bounce escalation, (2) late-cycle ambiguity,
        # (3) base rule. Most restrictive check first.
        if event.prior_bounce_count > 3:
            return Tier1Result(
                action="ESCALATE_TO_HUMAN",
                is_ambiguous=False,
                reason="high_prior_bounce_count_escalate",
            )
        if event.days_since_salary_credit > 15:
            # Salary was credited > 15 days ago — funds should be available; ambiguous
            return Tier1Result(
                action=None,
                is_ambiguous=True,
                reason="late_cycle_insufficient_funds_ambiguous",
            )
        return Tier1Result(
            action="SCHEDULE_POST_SALARY",
            is_ambiguous=False,
            reason="debit_before_salary_credit",
        )

    # --- AFA_REQUIRED ---
    if code == "AFA_REQUIRED":
        threshold = _get_afa_threshold(event, config)
        borderline_lower = threshold * (1 - _BORDERLINE_PCT)
        if event.amount >= threshold:
            return Tier1Result(
                action="SEND_UPI_INTENT_PUSH",
                is_ambiguous=False,
                reason="afa_threshold_exceeded",
            )
        if event.amount >= borderline_lower:
            # Within 10% below threshold — treat as borderline
            return Tier1Result(
                action=None,
                is_ambiguous=True,
                reason="borderline_afa_threshold",
            )
        # Below threshold but AFA code — system/data inconsistency; route to Tier-2
        return Tier1Result(
            action=None,
            is_ambiguous=True,
            reason="afa_code_below_threshold_inconsistency",
        )

    # --- MANDATE_PAUSED ---
    if code == "MANDATE_PAUSED":
        return Tier1Result(
            action="SEND_HINGLISH_NUDGE",
            is_ambiguous=False,
            reason="24h_pre_debit_notice_triggered_pause",
        )

    # --- BANK_TECHNICAL_DECLINE ---
    if code == "BANK_TECHNICAL_DECLINE":
        max_att = _max_attempts(event, config)
        if event.attempt_number >= max_att:
            return Tier1Result(
                action="ESCALATE_TO_HUMAN",
                is_ambiguous=False,
                reason=f"max_retry_attempts_reached_{max_att}",
            )
        return Tier1Result(
            action="RETRY_AFTER_BACKOFF",
            is_ambiguous=False,
            reason="bank_technical_failure_safe_to_retry",
        )

    # --- NON_REVOCABLE_HARD_DECLINE ---
    if code == "NON_REVOCABLE_HARD_DECLINE":
        return Tier1Result(
            action="ESCALATE_TO_HUMAN",
            is_ambiguous=False,
            reason="non_revocable_mandate_no_auto_retry",
        )

    # --- MANDATE_EXPIRED ---
    if code == "MANDATE_EXPIRED":
        return Tier1Result(
            action="SEND_MANDATE_RENEWAL_LINK",
            is_ambiguous=False,
            reason="mandate_token_expired_new_registration_required",
        )

    # --- UNKNOWN (any unrecognised code) ---
    return Tier1Result(
        action=None,
        is_ambiguous=True,
        reason="unknown_decline_code",
    )
