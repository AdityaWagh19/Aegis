# Compliance — Aegis

> **Status:** Canonical reference | This document governs all compliance gate implementation.
> Never modify compliance rules without updating this document first.

---

## Why Compliance is Unconditional

The compliance gate is not a feature — it is an architectural constraint. Three properties that must hold at all times:

1. **It is a pure function.** Same inputs always produce the same output, with no dependency on LLM state, session state, or configuration flags.
2. **It is structurally separate from Tier-1 and Tier-2.** It receives a proposed action; it does not generate one. Nothing downstream reads the proposed action directly — only the gate's `final_action` output reaches the executor.
3. **It cannot be configured off.** There is no feature flag, environment variable, or API parameter that disables the compliance gate. It is an unconditional code path.

The compliance-gate override moment — "the LLM proposed a retry, the gate blocked it, and that block is logged" — is the headline demo beat and the most defensible engineering decision in the submission.

---

## The Six Failure Categories (Canonical Reference)

Every rule in Tier-1, every Tier-2 prompt, and every compliance rule derives from this table. This is the only authoritative copy.

| Code | Category | Root Cause | Correct Action |
|---|---|---|---|
| `INSUFFICIENT_FUNDS` | Insufficient balance | Debit attempted before salary credit | `SCHEDULE_POST_SALARY` — reschedule to post-salary window, not a blind D+1 |
| `AFA_REQUIRED` | Above AFA threshold | NPCI blocks silent auto-debit above Rs. 15,000 | `SEND_UPI_INTENT_PUSH` — trigger explicit approval, never silent retry |
| `MANDATE_PAUSED` | Paused after 24h alert | RBI-mandated notice triggered a pause | `SEND_HINGLISH_NUDGE` — loss-aversion framing before mandate lapses |
| `BANK_TECHNICAL_DECLINE` | Bank-side technical failure | Timeout / bank downtime | `RETRY_AFTER_BACKOFF` — safe to retry once after backoff window |
| `NON_REVOCABLE_HARD_DECLINE` | Loan EMI, 2nd hard decline | Cannot legally auto-retry | `ESCALATE_TO_HUMAN` — zero further auto-retries, unconditionally |
| `MANDATE_EXPIRED` | Token/mandate lapsed | e-mandate validity window passed | `SEND_MANDATE_RENEWAL_LINK` — new registration, not a retry |

---

## The Action Allow-List (Canonical Reference)

Tier-2 (Groq/Llama) can only propose actions from this list. Pydantic schema validation enforces this — any response outside the enum is rejected and falls back to `ESCALATE_TO_HUMAN`.

```python
ALLOWED_ACTIONS = [
    "RETRY_AFTER_BACKOFF",          # Safe to retry after a delay
    "SCHEDULE_POST_SALARY",         # Reschedule to post-salary window
    "SEND_UPI_INTENT_PUSH",         # AFA-required: request explicit approval
    "SEND_MANDATE_RENEWAL_LINK",    # Expired mandate: new registration required
    "SEND_HINGLISH_NUDGE",          # Paused mandate: loss-aversion message
    "ESCALATE_TO_HUMAN",            # Non-revocable hard decline: no further auto-action
    "NO_ACTION_MONITORING",         # Monitor only, no immediate action
]

RETRY_ACTIONS = [
    "RETRY_AFTER_BACKOFF",
    "SCHEDULE_POST_SALARY",
]
```

---

## The Four Compliance Rules

These rules are enforced unconditionally by the compliance gate, in order. All four checks run on every proposed action.

---

### Rule 1 — Non-Revocable Mandate Hard Decline

**Trigger:** `is_revocable == False` AND `decline_code == "NON_REVOCABLE_HARD_DECLINE"`

**Legal basis:** Loan EMIs and certain insurance mandates cannot be automatically retried after a hard decline. Auto-retrying creates legal exposure for the lender.

**Gate behaviour:** Any proposed action other than `ESCALATE_TO_HUMAN` is rejected. No exceptions. Not configurable.

**Violation rule string:** `"non_revocable_mandate_no_auto_retry"`

---

### Rule 2 — Max Retry Attempts Cap

**Trigger:** `attempt_number >= MAX_RETRY_ATTEMPTS[mandate_type]` AND proposed action is in `RETRY_ACTIONS`

**Retry caps (from `compliance_config.yaml`):**
- `UPI_AUTOPAY`: 3 maximum automatic retries
- `ENACH`: 2 maximum automatic retries (higher bounce fee makes over-retrying costly)

**Legal basis:** Repeated auto-debits on insufficient-balance accounts accumulate NACH bounce fees (Rs. 200–500 per bounce for e-NACH). Caps protect the consumer.

**Gate behaviour:** Reject the retry action; escalate to human.

**Violation rule string:** `"max_retry_attempts_exceeded_{max_attempts}"`

---

### Rule 3 — AFA Threshold Routing

**Trigger:** `amount > AFA_THRESHOLD` AND proposed action is in `RETRY_ACTIONS`

**AFA thresholds (from `compliance_config.yaml`):**
- General: Rs. 15,000
- SIP / Insurance / Credit Cards: Rs. 1,00,000

**Legal basis:** NPCI mandates that silent auto-debits above the AFA threshold are blocked. The customer must explicitly approve the debit via a UPI-intent push. A silent retry violates NPCI rules.

**Gate behaviour:** Reject the retry action; redirect to `SEND_UPI_INTENT_PUSH`.

**Violation rule string:** `"afa_threshold_requires_intent_push_{threshold}"`

---

### Rule 4 — 24h Pre-Debit Notice Active

**Trigger:** `decline_code == "MANDATE_PAUSED"` AND proposed action is in `RETRY_ACTIONS`

**Legal basis:** RBI mandates that customers receive a 24h notification before a recurring debit. If the customer paused the mandate in response to that notification, the pause is a legal exercise of customer rights. Retrying during this window violates RBI rules.

**Gate behaviour:** Reject the retry action; redirect to `SEND_HINGLISH_NUDGE` or `ESCALATE_TO_HUMAN`.

**Violation rule string:** `"24h_pre_debit_notice_no_retry"`

---

## Compliance Gate Implementation

```python
class ComplianceGate:
    """
    Unconditional compliance enforcement.
    Cannot be bypassed by configuration, LLM output, or user action.
    Pure function: same inputs always produce the same output.
    """

    def check(self, event: MandateEvent, proposed_action: str) -> ComplianceResult:
        # Rule 1: Non-revocable mandate hard decline
        if not event.is_revocable and event.decline_code == "NON_REVOCABLE_HARD_DECLINE":
            if proposed_action != "ESCALATE_TO_HUMAN":
                return ComplianceResult(
                    approved=False,
                    final_action="ESCALATE_TO_HUMAN",
                    violation_blocked=True,
                    violation_rule="non_revocable_mandate_no_auto_retry"
                )

        # Rule 2: Max retry attempts exceeded
        max_attempts = MAX_RETRY_ATTEMPTS.get(event.mandate_type, 2)
        if event.attempt_number >= max_attempts and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="ESCALATE_TO_HUMAN",
                violation_blocked=True,
                violation_rule=f"max_retry_attempts_exceeded_{max_attempts}"
            )

        # Rule 3: AFA threshold — must use UPI intent push
        threshold = self._get_afa_threshold(event)
        if event.amount > threshold and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="SEND_UPI_INTENT_PUSH",
                violation_blocked=True,
                violation_rule=f"afa_threshold_requires_intent_push_{threshold}"
            )

        # Rule 4: 24h pre-debit notice active
        if event.decline_code == "MANDATE_PAUSED" and proposed_action in RETRY_ACTIONS:
            return ComplianceResult(
                approved=False,
                final_action="SEND_HINGLISH_NUDGE",
                violation_blocked=True,
                violation_rule="24h_pre_debit_notice_no_retry"
            )

        return ComplianceResult(
            approved=True,
            final_action=proposed_action,
            violation_blocked=False,
            violation_rule=None
        )

    def _get_afa_threshold(self, event: MandateEvent) -> int:
        if getattr(event, 'product_category', None) in ("sip", "insurance"):
            return AFA_THRESHOLD_SIP_INSURANCE
        return AFA_THRESHOLD_GENERAL
```

---

## `compliance_config.yaml` Specification

```yaml
# compliance_config.yaml
# This file is committed to the repository.
# Do not store secrets here. Thresholds only.

afa_threshold_general: 15000          # INR — NPCI general rule
afa_threshold_sip_insurance: 100000   # INR — NPCI SIP/insurance/credit card rule

max_retry_attempts:
  UPI_AUTOPAY: 3
  ENACH: 2

pre_debit_notice_window_hours: 24     # RBI mandatory notice window
```

---

## ComplianceResult Schema

```python
class ComplianceResult(BaseModel):
    approved: bool
    final_action: str           # The action that will actually execute
    violation_blocked: bool     # True if a violation was caught and overridden
    violation_rule: str | None  # The rule string that was triggered, if any
```

---

## Proving the Gate Cannot Be Bypassed

The answer to "how do you know the compliance gate cannot be bypassed?" during the panel round:

1. **It is a pure function.** Every unit test proves that for specific inputs, the output is always the same — there is no code path that produces different behaviour.
2. **It has a unit test for every rule in isolation.** Each of the four rules has a test proving it activates correctly and a test proving that a compliant action passes through.
3. **It is structurally separate from Tier-1 and Tier-2.** It receives a proposed action; it does not generate one. The action executor reads only `compliance_result.final_action` — never `proposed_action`.
4. **Its output is the only input to the executor.** Nothing downstream reads the proposed action directly.
5. **Integration test:** A deliberate violation batch is run during evaluation (Day 11) and the assertion `compliance_violations_executed == 0` is enforced programmatically.

---

## Compliance AFA Threshold Reference

| Mandate / Product Category | AFA Threshold | Config Key |
|---|---|---|
| General (subscriptions, SaaS, OTT) | Rs. 15,000 | `afa_threshold_general` |
| SIP, insurance, credit card payments | Rs. 1,00,000 | `afa_threshold_sip_insurance` |

---

## Retry Cap Reference

| Mandate Type | Max Automatic Retries | Config Key |
|---|---|---|
| UPI_AUTOPAY | 3 | `max_retry_attempts.UPI_AUTOPAY` |
| ENACH | 2 | `max_retry_attempts.ENACH` |

---

## Open Design Decision — AFA Threshold Detection

**Question (from §32 Open Questions):** Should the SIP/insurance AFA threshold be detected from `mandate_type` or a separate `product_category` field?

**Current assumption:** Add a `product_category` field to `MandateEvent` (values: `"subscription"`, `"loan_emi"`, `"sip"`, `"insurance"`). AFA threshold is looked up from `compliance_config.yaml` based on this field. If the field is absent, default to `afa_threshold_general`.

**Impact:** Affects `MandateEvent` schema in `models/mandate_event.py` and `ComplianceGate._get_afa_threshold()`.

---

*Source: Master_Aegis.md §7, §9 Feature 4, §16, §25 | Last updated: 2026-08-23*
