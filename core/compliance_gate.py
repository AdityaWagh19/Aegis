# core/compliance_gate.py
"""
Compliance Gate — unconditional NPCI/RBI rule enforcement.

INVARIANTS:
1. Pure function: same inputs always produce the same output.
2. No imports from core.tier1_engine or core.tier2_agent.
3. Cannot be configured off — no feature flag, env var, or API param disables it.
4. Its output (final_action) is the ONLY input to the action executor.
"""
from models.mandate_event import MandateEvent, RETRY_ACTIONS
from models.recovery_decision import ComplianceResult
from config.loader import ComplianceConfig, load_config


class ComplianceGate:

    def __init__(self, config: ComplianceConfig | None = None):
        self._cfg = config or load_config()

    def check(self, event: MandateEvent, proposed_action: str) -> ComplianceResult:
        """
        Enforce all four compliance rules in order.
        Returns a ComplianceResult with the final_action that may execute.
        """
        # Rule 1: Non-revocable mandate — only ESCALATE_TO_HUMAN is permitted
        # SCOPE NOTE: This rule triggers only when BOTH is_revocable=False AND
        # decline_code == "NON_REVOCABLE_HARD_DECLINE". This is intentional:
        # is_revocable=False is set by the NBFC for loan EMI mandates; the
        # NON_REVOCABLE_HARD_DECLINE code confirms the specific hard-decline event.
        # A non-revocable mandate receiving a BANK_TECHNICAL_DECLINE (transient)
        # may still receive RETRY_AFTER_BACKOFF — the NBFC has opted in to that
        # behaviour via the is_revocable flag. If broader protection is required,
        # change the condition to: `if not event.is_revocable:`
        if not event.is_revocable and event.decline_code == "NON_REVOCABLE_HARD_DECLINE":
            if proposed_action != "ESCALATE_TO_HUMAN":
                return ComplianceResult(
                    approved=False,
                    final_action="ESCALATE_TO_HUMAN",
                    violation_blocked=True,
                    violation_rule="non_revocable_mandate_no_auto_retry",
                )

        # Rule 2: Max retry attempts — cap retries per mandate type
        max_attempts = self._get_max_attempts(event)
        if event.attempt_number >= max_attempts and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="ESCALATE_TO_HUMAN",
                violation_blocked=True,
                violation_rule=f"max_retry_attempts_exceeded_{max_attempts}",
            )

        # Rule 3: AFA threshold — silent retry above threshold violates NPCI rules
        threshold = self._get_afa_threshold(event)
        if event.amount > threshold and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="SEND_UPI_INTENT_PUSH",
                violation_blocked=True,
                violation_rule=f"afa_threshold_requires_intent_push_{threshold}",
            )

        # Rule 4: 24h pre-debit notice — retrying on a paused mandate violates RBI rules
        if event.decline_code == "MANDATE_PAUSED" and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="SEND_HINGLISH_NUDGE",
                violation_blocked=True,
                violation_rule="24h_pre_debit_notice_no_retry",
            )

        # All rules passed
        return ComplianceResult(
            approved=True,
            final_action=proposed_action,
            violation_blocked=False,
            violation_rule=None,
        )

    def _get_max_attempts(self, event: MandateEvent) -> int:
        if event.mandate_type == "UPI_AUTOPAY":
            return self._cfg.max_retry_attempts.UPI_AUTOPAY
        return self._cfg.max_retry_attempts.ENACH

    def _get_afa_threshold(self, event: MandateEvent) -> int:
        if event.product_category in ("sip", "insurance"):
            return self._cfg.afa_threshold_sip_insurance
        return self._cfg.afa_threshold_general
