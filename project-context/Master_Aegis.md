# Master Project Document — Aegis
### Compliant UPI Autopay / e-NACH Failure Diagnosis & Recovery Agent

> **Revision:** 1.0 | **Track:** 03 — AI Revenue Recovery
> **Source PRD:** `PRD_Aegis.md` | **Composite Win Probability:** 8.5/10 | **Internship Signal:** 8.5–9/10

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Vision & Philosophy](#2-vision--philosophy)
3. [Problem Statement](#3-problem-statement)
4. [Design Principles](#4-design-principles)
5. [User Personas](#5-user-personas)
6. [Product Goals & Anti-Goals](#6-product-goals--anti-goals)
7. [Core Concepts & Mental Models](#7-core-concepts--mental-models)
8. [User Journey & Workflows](#8-user-journey--workflows)
9. [Feature Specifications](#9-feature-specifications)
10. [Information Architecture](#10-information-architecture)
11. [UX & Interaction Design](#11-ux--interaction-design)
12. [System Architecture](#12-system-architecture)
13. [Data Architecture](#13-data-architecture)
14. [AI/ML Architecture](#14-aiml-architecture)
15. [APIs & Integrations](#15-apis--integrations)
16. [Security & Compliance](#16-security--compliance)
17. [Cost & Scalability Considerations](#17-cost--scalability-considerations)
18. [Technical Stack & Infrastructure](#18-technical-stack--infrastructure)
19. [State Management & Data Flow](#19-state-management--data-flow)
20. [Backend Architecture](#20-backend-architecture)
21. [Frontend Architecture](#21-frontend-architecture)
22. [Testing Strategy](#22-testing-strategy)
23. [Observability & Monitoring](#23-observability--monitoring)
24. [Deployment Strategy](#24-deployment-strategy)
25. [Engineering Constraints](#25-engineering-constraints)
26. [Performance Requirements](#26-performance-requirements)
27. [Success Metrics & KPIs](#27-success-metrics--kpis)
28. [Demo Flow](#28-demo-flow)
29. [MVP Scope](#29-mvp-scope)
30. [Post-MVP Roadmap](#30-post-mvp-roadmap)
31. [Risks & Mitigations](#31-risks--mitigations)
32. [Open Questions](#32-open-questions)
33. [Glossary](#33-glossary)

---

## 1. Executive Summary

**Aegis** is a compliant, two-tier failure diagnosis and recovery agent for UPI Autopay and e-NACH mandates used by Indian subscription businesses and NBFCs. It answers one of the most painful, unsolved problems in Indian fintech: *"Why did my customer's recurring payment fail, and what is the legally compliant action I should take next?"*

**The core insight:** Every global dunning tool (Stripe Smart Retries, Churnkey, Churn Buster, Butter Payments) is built for card rails. None of them model NPCI mandate mechanics, RBI compliance rules, or the structural difference between UPI Autopay (zero consumer bounce fee) and NACH (Rs. 200–500 consumer penalty per bounce). Aegis is built exclusively for this context.

**What it does in one breath:** Ingest a batch of failed/at-risk mandate events → a deterministic Tier-1 rule engine resolves ~65–75% of cases instantly → ambiguous/composite cases go to a Claude Tier-2 reasoning step constrained to a fixed action allow-list → all proposed actions pass through a non-LLM compliance gate that cannot be bypassed → actions execute against Razorpay test-mode APIs → every decision is appended to an immutable audit log → a dashboard reports recovery rate, rupees recovered vs. at risk, and compliance violations caught.

**Why it wins:** It is explicitly named as a direction on the Buildathon page ("Mandate retry sequencer," "Hinglish voice recovery"), Razorpay's engineering blog reportedly published an internal playbook on this problem immediately before the hackathon, and no global competitor has built this. The compliance-gate moment — Claude proposes a retry, the deterministic gate overrides it, the override is logged — is the most memorable and defensible demo beat in the entire submission.

---

## 2. Vision & Philosophy

### North Star
Build the first India-native, compliance-aware dunning intelligence layer that treats UPI Autopay and e-NACH as first-class citizens — not bolted-on edge cases of a card-first system.

### Core Philosophical Commitment
> "The rule engine decides. Claude explains and drafts. Compliance is unconditional."

Three specific implications:
1. **Tier-1 is the workhorse.** If Tier-1 (deterministic rules) is routing more than 30% of cases to Claude (Tier-2), the rule engine isn't doing its job. That's a negative signal, not sophistication.
2. **The compliance gate is unconditional.** No LLM output can bypass it. If Claude proposes a retry on a non-revocable mandate after two hard declines, the gate blocks it, logs the override, and escalates to human. This is your headline demo moment.
3. **Honesty is the strategy.** Report recovery rate on the held-out test set (the batch not seen while writing rules). Report false-escalation rate. Show compliance violations caught vs. those that reached execution (must be zero of the latter). Honest metrics beat impressive-looking ones you can't defend.

### Design Philosophy
1. **Six categories, done well.** Six well-modeled failure categories beat twenty shallow ones.
2. **Compliant by architecture.** The compliance gate is an unconditional code path — it cannot be configured off, it cannot be bypassed by a prompt.
3. **Majority deterministic.** Approximately 65–75% of cases resolve via Tier-1 without touching an LLM. This is a feature, explicitly tracked on the dashboard, and a core "AI Judgment" rubric signal.
4. **India-mandate-aware by default.** AFA thresholds, 24h pre-debit notice rules, non-revocable mandate constraints, and salary-cycle-aware retry timing are first-class concerns, not footnotes.

---

## 3. Problem Statement

### The Revenue Leak
Indian subscription and lending businesses lose **10–20%+ of recurring revenue** to UPI Autopay / e-NACH mandate failures. The failure modes are structurally Indian and not addressed by any existing global tool:

| Failure Type | Example | Why Global Tools Fail |
|---|---|---|
| Insufficient funds at debit time | Salary credited on the 5th, debit attempted on the 3rd | Card retry logic assumes funds are available immediately after a failed attempt |
| AFA threshold (NPCI rule) | Auto-debit attempted for Rs. 18,000; NPCI blocks silent debit above Rs. 15,000 | Card rails have no equivalent concept |
| RBI mandatory 24h pre-debit notice | Customer gets the TPAP notification and pauses the mandate | No global equivalent; the pause is legal and expected |
| Non-revocable loan mandates | EMI mandate for a home loan cannot legally be auto-retried after a second hard decline | Card-rail assumption: always retry |
| NACH bounce fee asymmetry | NACH bounce costs the consumer Rs. 200–500; UPI Autopay bounce costs zero | Different retry economics not modeled in any global tool |
| Mandate expiry | e-mandate validity window lapses silently | Card retries work indefinitely; mandate tokens expire |

### The Competitive Gap
Every global dunning tool — Stripe Smart Retries, Churnkey, Churn Buster, ProsperStack, Butter Payments — is card-rail native. None of them model:
- NPCI mandate mechanics
- Non-revocable loan mandate constraints
- The salary-cycle-aware retry window
- UPI Autopay vs. NACH structural differences
- The AFA threshold routing rule
- The 24h pre-debit notice mandatory pause

### Business Signal
This is not a hypothetical problem:
- It is explicitly named on the Buildathon page as an example direction
- Razorpay's own engineering blog reportedly published a playbook on this problem before the hackathon — a signal it is a live internal priority
- The market: every NBFC, subscription SaaS, OTT platform, insurance company, and fitness app on UPI Autopay or e-NACH in India is affected

---

## 4. Design Principles

| # | Principle | Operational Meaning |
|---|---|---|
| **P1** | Majority deterministic | Tier-1 resolves ~65–75% of cases; LLM handles only the ambiguous remainder |
| **P2** | Compliance is unconditional | The compliance gate cannot be bypassed by any LLM output, configuration, or user action |
| **P3** | Six categories, done well | Only the six failure categories in the taxonomy are modeled; depth beats breadth |
| **P4** | Salary-cycle-aware | Retry timing is informed by days-since-salary-credit, not a blind D+1/D+3 schedule |
| **P5** | Held-out evaluation | Metrics are reported on a test slice not seen while writing rules or prompts |
| **P6** | Human escalation is a feature | Non-revocable mandates escalating to human review is the correct outcome, not a failure |
| **P7** | Hinglish as a first-class output | Recovery messages drafted by Claude are in Hinglish by default — India-first, not translated |
| **P8** | Transparent AI judgment | Every Tier-2 decision shows: rationale, confidence, alternatives considered, compliance result |

---

## 5. User Personas

### Persona 1 — Finance-Ops User at an NBFC (Primary)
- **Name:** Meera, Collections Analyst at a lending NBFC
- **Context:** Manages a portfolio of 5,000+ active EMI mandates via Razorpay; currently handles failed mandates by running blind D+1/D+3 retries and manual collections calls
- **Pain Points:**
  - No visibility into *why* a mandate failed (just a raw decline code)
  - Fixed retry schedule causes unnecessary NACH bounce fees when funds are genuinely not available
  - Non-revocable loan mandates occasionally get blindly retried, creating legal exposure
  - No automated Hinglish customer communication for paused mandates
- **Goal:** Load a batch of failed mandates, see what's recoverable and what requires human action, and send appropriate customer nudges — in one workflow
- **How Aegis helps:** Meera loads a CSV, clicks Run Recovery, sees 70%+ resolved in under a second with reasons, sees 3 ambiguous cases routed to Claude with Hinglish messages drafted, sees the non-revocable EMI case escalated to human with the compliance rule cited

### Persona 2 — Subscription SaaS Finance Team (Primary)
- **Name:** Rajesh, CFO of a B2B SaaS company on UPI Autopay
- **Context:** 400 subscribers, ~14% monthly payment failure rate; manually reviews each failure
- **Pain Point:** Can't distinguish "retry tomorrow" (BANK_TECHNICAL_DECLINE) from "send a new mandate registration link" (MANDATE_EXPIRED) — they look the same in the raw webhook event
- **Goal:** Automate the triage of failed mandates so the finance team only sees cases that genuinely need human judgment

### Persona 3 — Razorpay Revenue Recovery / Agent Studio Team (Secondary)
- **Name:** Ananya, PM on Razorpay's Subscription Recovery Agent product
- **Context:** Building agent-native recovery features for the Subscriptions product; needs a reference architecture for compliant automated dunning
- **Goal:** Understand how a two-tier compliant recovery agent should be architected
- **How Aegis helps:** Provides a working reference architecture with compliance gate design that is directly applicable to Razorpay's own roadmap

### Persona 4 — Hackathon Judge (Evaluator)
- **Name:** Senior Razorpay Engineer or PM
- **What they want to see:** A non-revocable mandate correctly refused and escalated to human; a live Tier-1 vs. Tier-2 split; a compliance-violations-caught count greater than zero but zero that reached execution; honest held-out metrics

---

## 6. Product Goals & Anti-Goals

### Goals

| ID | Goal |
|---|---|
| G1 | Given a batch of 50+ synthetic failed/at-risk mandate events, correctly classify root cause using a deterministic rule engine for ~65–75% of cases |
| G2 | For ambiguous/composite cases, use Claude — constrained to a fixed action allow-list and structured JSON output — to propose a compliant recovery action plus a Hinglish customer message |
| G3 | Enforce hard compliance rules (AFA thresholds, 24h pre-debit notice, non-revocable mandate escalation-only, max retry attempts) via a deterministic compliance gate that Claude cannot override |
| G4 | Execute chosen actions against Razorpay's test-mode Subscriptions / Payment Links API and log every decision to an append-only audit trail |
| G5 | Report honest held-out metrics: recovery rate by failure category, rupees recovered vs. at risk, zero compliance violations reaching execution, false-escalation rate |
| G6 | Demonstrate at least one deliberate "graceful failure" moment live — a non-revocable EMI mandate correctly refusing a third retry and escalating to human |

### Anti-Goals (Hard Cuts)

| Anti-Goal | Reason |
|---|---|
| Production-grade bandit/survival-analysis/RL optimizer as core deliverable | No real convergence to show on synthetic data; invites unanswerable "how do you know this converges?" question |
| Real WhatsApp/voice/telephony integration | A mocked notification stub is sufficient and expected; judges care about decision logic, not a WhatsApp API key |
| Real customer PII or bank data | 100% synthetic, generated with realistic distributions |
| Covering every NPCI/bank decline code | Six well-modeled categories beat twenty shallow ones |
| Routing more than ~30% of cases to Claude (Tier-2) | If more than 30% hit Tier-2, the rule engine isn't doing its job — that is a negative signal |

---

## 7. Core Concepts & Mental Models

### The Six Failure Categories (MVP Scope — Exactly These Six)

This taxonomy is the intellectual core of the product. Every rule in Tier-1, every Claude prompt in Tier-2, and every compliance rule in the gate is derived from this table.

| Code | Category | Root Cause | Correct Action |
|---|---|---|---|
| `INSUFFICIENT_FUNDS` | Insufficient balance | Debit attempted before salary credit | Reschedule to post-salary-date window — not a blind D+1 |
| `AFA_REQUIRED` | Above Rs. 15,000 AFA threshold | NPCI blocks silent auto-debit above threshold | Trigger UPI-intent push requiring explicit approval — never silent retry |
| `MANDATE_PAUSED` | Paused after 24h pre-debit alert | RBI-mandated notice triggered a pause | Loss-aversion-framed Hinglish nudge before the mandate lapses |
| `BANK_TECHNICAL_DECLINE` | Bank-side technical failure | Timeout / bank downtime | Safe to retry once, after a backoff window |
| `NON_REVOCABLE_HARD_DECLINE` | Loan EMI, 2nd hard decline | Cannot legally auto-retry a non-revocable mandate | Escalate to human — zero further auto-retries |
| `MANDATE_EXPIRED` | Token/mandate lapsed | e-mandate validity window passed | Send a new mandate registration link, not a retry |

**Implementation note:** This table doubles as a strong demo artifact. Put it on screen during the Tier-1 demo beat.

### The Two-Tier Architecture Mental Model

```
[ALL FAILED MANDATES]
         |
    Tier 1: Deterministic Rule Engine
    (decline_code lookup table)
         |
    65-75% resolved here instantly
         |
    25-35% ambiguous/composite cases
         |
    Tier 2: Claude Reasoning Agent
    (structured output ONLY, fixed action allow-list)
         |
    ALL proposed actions
         |
    Compliance Gate (unconditional, non-LLM)
    AFA rules, 24h notice, non-revocable rules
         |
    Approved actions only
         |
    Action Executor (Razorpay test-mode APIs)
         |
    Append-only Audit Log
```

### The Compliance Gate as a Non-Negotiable Boundary

```
+--------------------------------+
|    REASONING ZONE              |
|  Tier 1: lookup-table logic    |
|  Tier 2: Claude structured     |
|  output from fixed allow-list  |
+--------------------------------+
           |
           | proposed action (from allow-list)
           v
+================================+
||   COMPLIANCE GATE             ||
||   (unconditional, no LLM)     ||
||   max_retry_attempts          ||
||   24h pre-debit notice        ||
||   AFA threshold routing       ||
||   non-revocable -> escalate   ||
+================================+
           |
           | approved action only
           v
+--------------------------------+
|    EXECUTION ZONE              |
|  Razorpay test-mode APIs       |
|  Mock notification stub        |
+--------------------------------+
```

### The Action Allow-List
Claude (Tier-2) can only propose actions from this fixed list. It cannot invent new actions:

```python
ALLOWED_ACTIONS = [
    "RETRY_AFTER_BACKOFF",           # Safe to retry after a delay
    "SCHEDULE_POST_SALARY",          # Reschedule to post-salary window
    "SEND_UPI_INTENT_PUSH",          # AFA-required: request explicit approval
    "SEND_MANDATE_RENEWAL_LINK",     # Expired mandate: new registration required
    "SEND_HINGLISH_NUDGE",           # Paused mandate: loss-aversion message
    "ESCALATE_TO_HUMAN",             # Non-revocable hard decline: no further auto-action
    "NO_ACTION_MONITORING",          # Monitor only, no immediate action
]
```

---

## 8. User Journey & Workflows

### Primary Workflow — Batch Recovery Run

```
Finance-ops user uploads a CSV of failed mandates (50-200 records)
         |
         | POST /api/v1/recovery/batch (multipart CSV)
         v
System validates CSV schema and generates mandate_events
         |
Tier-1 Rule Engine processes all records simultaneously
  - For each record: decline_code -> lookup -> action
  - ~65-75% resolved with a clear action
         |
Ambiguous/composite cases (25-35%) forwarded to Tier-2
         |
Claude Tier-2 processes each ambiguous case:
  - Input: {mandate_id, decline_code, customer_features, history}
  - Output: {action: <from allow-list>, message_hinglish: str, rationale: str, confidence: float}
         |
ALL actions (Tier-1 and Tier-2) pass through Compliance Gate:
  - Check: max_retry_attempts not exceeded
  - Check: 24h pre-debit notice rule
  - Check: AFA threshold routing
  - Check: non-revocable + hard decline -> escalation only
  - Violations: REJECTED, logged as "blocked by compliance gate"
         |
Approved actions execute:
  - Razorpay Subscriptions API (pause/resume/cancel)
  - Razorpay Payment Links API (new mandate / UPI-intent links)
  - Mock notification stub (logs "would send: <message>")
         |
Every decision appended to audit log (including compliance violations caught)
         |
Dashboard refreshes: recovery rate, Rs. recovered, tier split, violations
```

### Drill-Down Workflow — Single Mandate Detail

```
User clicks any mandate row in the dashboard
         |
Drawer opens showing:
  - mandate_id, customer_id, amount, mandate_type
  - decline_code and human-readable explanation
  - Tier that decided (1 or 2)
  - For Tier-2: Claude's rationale, confidence, alternatives considered
  - Compliance gate result (passed or rejected with rule cited)
  - Action taken and execution result
  - Hinglish message (if generated)
  - Audit log entry hash
```

### Graceful Failure Workflow — Non-Revocable Hard Decline

```
Mandate: type=ENACH, mandate_type=NON_REVOCABLE, attempt_number=2
         |
Tier-1: decline_code=NON_REVOCABLE_HARD_DECLINE -> action=ESCALATE_TO_HUMAN
         |
(But let's say Tier-2 is also consulted -- Claude proposes RETRY_AFTER_BACKOFF)
         |
Compliance Gate:
  - Rule: is_revocable=false AND attempt_number >= 2 -> REJECT
  - Proposed action: RETRY_AFTER_BACKOFF -> BLOCKED
  - Reason: "non_revocable_mandate_max_attempts_exceeded"
         |
Audit Log: records "Claude proposed RETRY_AFTER_BACKOFF; compliance gate rejected; escalated to human"
         |
Dashboard: shows this case under "Human Review" queue with compliance rule cited
```

---

## 9. Feature Specifications

### Feature 1 — Synthetic Mandate Event Generator

**Purpose:** Produce realistic synthetic mandate failure data to drive the demo, evaluation, and testing.

**User Value:** Enables honest, reproducible evaluation without real customer PII or bank data.

**Functional Requirements:**
- Generate 500-1,000 mandate events with realistic distributions
- Overall failure rate: ~14% (based on published bounce-rate statistics)
- Failure category distribution (of failed mandates):
  - INSUFFICIENT_FUNDS: 40%
  - BANK_TECHNICAL_DECLINE: 20%
  - MANDATE_PAUSED: 15%
  - AFA_REQUIRED: 10%
  - MANDATE_EXPIRED: 10%
  - NON_REVOCABLE_HARD_DECLINE: 5%
- Each record includes ground-truth correct_action label
- A held-out slice (20%) reserved before any rule-writing begins; never seen during development

**Mandate Event Schema:**
```python
class MandateEvent(BaseModel):
    mandate_id: str          # UUID
    customer_id: str
    amount: int              # INR, integer
    mandate_type: str        # "UPI_AUTOPAY" | "ENACH"
    decline_code: str        # One of the six taxonomy codes
    days_since_salary_credit: int   # 0-30
    prior_bounce_count: int         # 0-5
    is_revocable: bool              # False for loan mandates
    attempt_number: int             # 1-3
    timestamp: datetime
    correct_action: str             # Ground-truth label (for evaluation only)
```

**Generator Script:**
```python
from faker import Faker
import random

faker = Faker('en_IN')

DECLINE_CODE_DISTRIBUTION = {
    "INSUFFICIENT_FUNDS": 0.40,
    "BANK_TECHNICAL_DECLINE": 0.20,
    "MANDATE_PAUSED": 0.15,
    "AFA_REQUIRED": 0.10,
    "MANDATE_EXPIRED": 0.10,
    "NON_REVOCABLE_HARD_DECLINE": 0.05,
}

CORRECT_ACTIONS = {
    "INSUFFICIENT_FUNDS": "SCHEDULE_POST_SALARY",
    "BANK_TECHNICAL_DECLINE": "RETRY_AFTER_BACKOFF",
    "MANDATE_PAUSED": "SEND_HINGLISH_NUDGE",
    "AFA_REQUIRED": "SEND_UPI_INTENT_PUSH",
    "MANDATE_EXPIRED": "SEND_MANDATE_RENEWAL_LINK",
    "NON_REVOCABLE_HARD_DECLINE": "ESCALATE_TO_HUMAN",
}

def generate_mandate_event(is_held_out: bool = False) -> MandateEvent:
    decline_code = random.choices(
        list(DECLINE_CODE_DISTRIBUTION.keys()),
        weights=list(DECLINE_CODE_DISTRIBUTION.values())
    )[0]
    is_revocable = decline_code != "NON_REVOCABLE_HARD_DECLINE"
    return MandateEvent(
        mandate_id=str(uuid4()),
        amount=random.randint(500, 25000),
        mandate_type=random.choice(["UPI_AUTOPAY", "ENACH"]),
        decline_code=decline_code,
        days_since_salary_credit=random.randint(0, 28),
        prior_bounce_count=random.randint(0, 4),
        is_revocable=is_revocable,
        attempt_number=random.randint(1, 3),
        correct_action=CORRECT_ACTIONS[decline_code],
    )
```

**Testing Requirements:**
- Verify generated distribution matches target (within 5% tolerance)
- Verify held-out set is not used during rule development (enforced by code separation)

---

### Feature 2 — Tier-1: Deterministic Rule Engine

**Purpose:** Resolve ~65–75% of failed mandate cases instantly using a lookup-table approach, without any LLM call.

**User Value:** Fast, cheap, auditable resolution for the majority of cases. The headline "AI Judgment" demonstration — resist turning this into an ML model.

**Functional Requirements:**
- Accept a MandateEvent as input
- Look up decline_code in the taxonomy table
- Apply additional contextual rules (amount vs. AFA threshold, attempt_number, is_revocable, days_since_salary_credit)
- Return a Tier1Result: {action, reason, tier=1, confidence=1.0, is_ambiguous}
- Mark cases as ambiguous (is_ambiguous=True) when:
  - decline_code is not in the taxonomy (unknown code)
  - Multiple conditions overlap (e.g., INSUFFICIENT_FUNDS with prior_bounce_count > 3)
  - Amount is borderline relative to AFA threshold (within 10%)

**Rule Implementation:**
```python
AFA_THRESHOLD_GENERAL = 15000     # INR
AFA_THRESHOLD_SIP_INSURANCE = 100000  # INR
MAX_RETRY_ATTEMPTS = {
    "UPI_AUTOPAY": 3,
    "ENACH": 2,
}

def classify_mandate(event: MandateEvent, config: ComplianceConfig) -> Tier1Result:
    code = event.decline_code

    if code == "INSUFFICIENT_FUNDS":
        if event.prior_bounce_count > 3:
            return Tier1Result(action="ESCALATE_TO_HUMAN", tier=1,
                reason="repeated_insufficient_funds_high_risk", is_ambiguous=False)
        return Tier1Result(action="SCHEDULE_POST_SALARY", tier=1,
            reason="debit_before_salary_credit", is_ambiguous=False)

    elif code == "AFA_REQUIRED":
        threshold = AFA_THRESHOLD_SIP_INSURANCE if event.mandate_type == "ENACH" else AFA_THRESHOLD_GENERAL
        if event.amount > threshold:
            return Tier1Result(action="SEND_UPI_INTENT_PUSH", tier=1,
                reason=f"amount_{event.amount}_exceeds_afa_threshold_{threshold}", is_ambiguous=False)
        # Amount is borderline (within 10% of threshold) -> ambiguous
        if event.amount > threshold * 0.9:
            return Tier1Result(action=None, tier=1, is_ambiguous=True,
                reason="borderline_afa_threshold")

    elif code == "MANDATE_PAUSED":
        return Tier1Result(action="SEND_HINGLISH_NUDGE", tier=1,
            reason="mandate_paused_after_24h_notice", is_ambiguous=False)

    elif code == "BANK_TECHNICAL_DECLINE":
        max_attempts = MAX_RETRY_ATTEMPTS.get(event.mandate_type, 2)
        if event.attempt_number >= max_attempts:
            return Tier1Result(action="ESCALATE_TO_HUMAN", tier=1,
                reason="max_retry_attempts_exceeded", is_ambiguous=False)
        return Tier1Result(action="RETRY_AFTER_BACKOFF", tier=1,
            reason="bank_side_technical_failure", is_ambiguous=False)

    elif code == "NON_REVOCABLE_HARD_DECLINE":
        return Tier1Result(action="ESCALATE_TO_HUMAN", tier=1,
            reason="non_revocable_mandate_hard_decline", is_ambiguous=False)

    elif code == "MANDATE_EXPIRED":
        return Tier1Result(action="SEND_MANDATE_RENEWAL_LINK", tier=1,
            reason="mandate_token_expired", is_ambiguous=False)

    # Unknown decline code -> route to Tier-2
    return Tier1Result(action=None, tier=1, is_ambiguous=True, reason="unknown_decline_code")
```

**Non-Functional Requirements:**
- Tier-1 resolution latency < 5ms per record
- 0% LLM calls in Tier-1 — enforced at the code level (no imports from LLM modules)

**Testing Requirements:**
- Unit test each of the six categories with multiple input variations
- Unit test ambiguous routing conditions (unknown code, borderline AFA amount, high-bounce repeat)
- Verify Tier-1 handles all six codes without ever calling the LLM
- Measure actual Tier-1 resolution rate on the generated dataset (target: 65–75%)

---

### Feature 3 — Tier-2: Claude Reasoning Agent

**Purpose:** Handle the ambiguous/composite cases (25–35%) that Tier-1 cannot resolve deterministically.

**User Value:** Handles genuinely unclear cases with explainable reasoning rather than blind rules or a coin flip.

**Functional Requirements:**
- Only receives cases where Tier-1 set is_ambiguous=True
- Input to Claude: {mandate_id, decline_code, customer_features, history, allowed_actions}
- Output from Claude (structured JSON ONLY): {action: <from ALLOWED_ACTIONS>, message_hinglish: str, rationale: str, confidence: float, alternatives_considered: list}
- Claude CANNOT invent actions outside ALLOWED_ACTIONS — enforced by Pydantic schema validation on the output
- The Hinglish message is drafted by Claude following a loss-aversion framing template
- If Claude's structured output is malformed: fall back to ESCALATE_TO_HUMAN, log the failure

**Claude Prompt Architecture:**
```python
SYSTEM_PROMPT = """
You are a mandate recovery specialist for an Indian NBFC/subscription business.
You analyze failed UPI Autopay and e-NACH mandate cases and propose recovery actions.

IMPORTANT CONSTRAINTS:
1. You MUST call the propose_recovery_action tool. Do not respond in plain text.
2. You can ONLY propose actions from this list: {allowed_actions}
3. The action you propose will pass through a compliance gate before execution.
   Do not worry about compliance — just propose the best customer-centric action.
4. Draft the Hinglish message in a warm, loss-aversion framing.
   Example: "Aapka subscription abhi bhi active hai — sirf ek step aur!"
5. If you are not confident (confidence < 0.6), set action to ESCALATE_TO_HUMAN.
"""

PROPOSE_RECOVERY_TOOL = {
    "name": "propose_recovery_action",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ALLOWED_ACTIONS,
                "description": "The recovery action to take"
            },
            "message_hinglish": {
                "type": "string",
                "description": "Customer-facing message in Hinglish (Hindi-English mix)"
            },
            "rationale": {
                "type": "string",
                "description": "Why you chose this action, in 1-2 sentences"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0
            },
            "alternatives_considered": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["action", "message_hinglish", "rationale", "confidence"]
    }
}
```

**Hinglish Message Templates (seeded to Claude, not hardcoded):**
```python
HINGLISH_TEMPLATES = {
    "MANDATE_PAUSED": "Aapka [service_name] subscription abhi bhi active hai! Bas ek click se payment complete karein aur service continue karein.",
    "AFA_REQUIRED": "Aapki payment ke liye ek-baar approval chahiye. Link pe click karein — 2 minute ka kaam hai!",
    "INSUFFICIENT_FUNDS": "Salary aane ke baad aapka payment automatically ho jayega. Koi action ki zaroorat nahi!",
}
```

**Non-Functional Requirements:**
- Tier-2 resolution latency P95 < 3,000ms (LLM call included)
- Tier-2 must never exceed 35% of the total batch (if it does, Tier-1 rules need improvement)
- If LLM call fails: fall back to ESCALATE_TO_HUMAN with reason "tier2_failure"

**Testing Requirements:**
- Unit: verify Pydantic schema rejects any action outside ALLOWED_ACTIONS
- Integration: run Tier-2 on 10 known-ambiguous cases; verify action is always in ALLOWED_ACTIONS
- Verify Hinglish message is generated for all MANDATE_PAUSED and AFA_REQUIRED cases

---

### Feature 4 — Compliance Gate

**Purpose:** Ensure no recovery action violates NPCI/RBI compliance rules, regardless of what Tier-1 or Tier-2 proposed.

**User Value:** This is the primary legal protection. It is also the most important demo moment — Claude proposing a non-compliant action, the gate overriding it, and the override being logged.

**Functional Requirements:**
- Receive a proposed action from Tier-1 or Tier-2
- Check ALL of the following rules unconditionally:
  1. **Max retry attempts:** If attempt_number >= max_retry_attempts[mandate_type], reject RETRY_AFTER_BACKOFF and SCHEDULE_POST_SALARY
  2. **24h pre-debit notice:** If mandate was paused within last 24 hours, reject any retry action; only SEND_HINGLISH_NUDGE or ESCALATE_TO_HUMAN are allowed
  3. **AFA threshold routing:** If amount > AFA_THRESHOLD and proposed action is RETRY_AFTER_BACKOFF or SCHEDULE_POST_SALARY, reject — must be SEND_UPI_INTENT_PUSH
  4. **Non-revocable + hard decline:** If is_revocable=False and decline_code=NON_REVOCABLE_HARD_DECLINE, only ESCALATE_TO_HUMAN is allowed — all other actions are rejected
- Return: ComplianceResult {approved: bool, final_action: str, violation_blocked: bool, violation_rule: str | null}
- If rejected: final_action = ESCALATE_TO_HUMAN, violation_blocked = True
- Log all compliance violations (even those that were caught and blocked)

**Compliance Rule Implementation:**
```python
class ComplianceGate:
    """Unconditional compliance enforcement. Cannot be bypassed."""

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

        return ComplianceResult(approved=True, final_action=proposed_action, violation_blocked=False)
```

**Non-Functional Requirements:**
- Compliance gate latency < 5ms (no network calls, no LLM calls)
- The gate is a pure function: same inputs -> same output, always
- The gate is independently unit-tested; every rule has a test proving it cannot be bypassed

**Compliance Guardrail Configuration:**
```yaml
# compliance_config.yaml
afa_threshold_general: 15000       # INR
afa_threshold_sip_insurance: 100000  # INR
max_retry_attempts:
  UPI_AUTOPAY: 3
  ENACH: 2
pre_debit_notice_window_hours: 24
```

**Testing Requirements (Critical):**
- Unit test every rule in isolation
- Unit test that Claude's structured output cannot bypass the gate
- Integration test: run a batch that includes at least one deliberate compliance violation; verify it is caught and logged, and zero violations reach execution
- The ability to say "we have tests proving the compliance gate can't be bypassed" is a strong answer in the panel round

---

### Feature 5 — Action Executor

**Purpose:** Execute the compliance-approved recovery action against Razorpay's test-mode APIs or the mock notification stub.

**Functional Requirements:**
- Route the final_action to the correct execution path:
  - RETRY_AFTER_BACKOFF: Razorpay Subscriptions API (resume/charge)
  - SCHEDULE_POST_SALARY: Razorpay Subscriptions API (pause + schedule resume)
  - SEND_UPI_INTENT_PUSH: Razorpay Payment Links API (UPI-intent link)
  - SEND_MANDATE_RENEWAL_LINK: Razorpay Payment Links API (new mandate registration)
  - SEND_HINGLISH_NUDGE: Mock notification stub (logs "would send: <message>")
  - ESCALATE_TO_HUMAN: Write to human_review_queue table, no API call
  - NO_ACTION_MONITORING: Log only, no API call
- Log execution result (success/failure/mock) to audit trail
- All Razorpay calls use test-mode API keys exclusively

**Razorpay Subscriptions API:**
```python
async def resume_subscription(subscription_id: str) -> dict:
    """Called for RETRY_AFTER_BACKOFF."""
    return await razorpay_client.subscriptions.resume({
        "subscription_id": subscription_id,
        "resume_at": "now"
    })

async def create_recovery_payment_link(event: MandateEvent, message: str) -> dict:
    """Called for SEND_UPI_INTENT_PUSH and SEND_MANDATE_RENEWAL_LINK."""
    return await razorpay_client.payment_links.create({
        "amount": event.amount * 100,  # Paise
        "currency": "INR",
        "description": f"Payment recovery — {event.mandate_id}",
        "notify": {"sms": False, "email": False},
        "notes": {
            "mandate_id": event.mandate_id,
            "recovery_action": "UPI_INTENT_PUSH"
        }
    })
```

**Mock Notification Stub:**
```python
def send_notification_mock(customer_id: str, message: str, channel: str) -> dict:
    """Logs the notification without actually sending it. Expected for hackathon."""
    logger.info(f"[MOCK NOTIFICATION] would send to {customer_id} via {channel}: {message}")
    return {"status": "mocked", "would_send": message, "channel": channel}
```

---

### Feature 6 — Append-Only Audit Log

**Purpose:** Record every decision, including tier that decided, compliance result, and outcome, in a tamper-evident append-only log.

**Functional Requirements:**
- Every mandate event (resolved or escalated) produces exactly one audit entry
- Entry fields: mandate_id, timestamp, tier_that_decided, proposed_action, compliance_check_result, final_action, outcome, rationale, hinglish_message_preview, alternatives_considered
- Audit log table enforces append-only (no UPDATE or DELETE at the database role level)

**Audit Entry Schema:**
```typescript
interface AuditEntry {
  entry_id: number;
  mandate_id: string;
  customer_id: string;
  timestamp: string;
  tier_that_decided: 1 | 2;
  decline_code: string;
  proposed_action: string;
  compliance_check_result: {
    approved: boolean;
    violation_blocked: boolean;
    violation_rule: string | null;
  };
  final_action: string;
  outcome: "executed" | "mocked" | "escalated" | "failed";
  rationale: string;
  confidence: number | null;
  hinglish_message_preview: string | null;
  alternatives_considered: string[] | null;
  razorpay_response: object | null;
}
```

---

### Feature 7 — Dashboard

**Purpose:** Provide finance-ops users and judges with a real-time view of recovery performance, tier split, and compliance violations.

**Functional Requirements:**
- **Front-page stat:** Rs. recovered / Rs. at risk (single large number, front and center)
- **Recovery rate by category:** Table with per-category recovery rate on the held-out batch
- **Tier-1 vs. Tier-2 split:** Percentage of cases resolved by each tier
- **Compliance violations caught:** Count of violations the gate caught; compliance violations that reached execution (must be 0)
- **Human review queue:** List of mandates escalated to human, with reason
- **Mandate detail drawer:** Click any mandate to see its full decision trail
- **Batch upload UI:** Drag-and-drop CSV upload, progress bar, then instant results

**Front Page Layout:**
```
+------------------------------------------------------------+
| Aegis                              [Upload New Batch]|
+---------------+----------------+-------------+-------------+
| Rs. RECOVERED | Rs. AT RISK    | RECOVERY %  | VIOLATIONS  |
| 2,34,500      | 5,12,000       | 45.8%       | CAUGHT: 3   |
|               |                |             | EXECUTED: 0 |
+---------------+----------------+-------------+-------------+
| TIER SPLIT              | RECOVERY BY CATEGORY             |
| Tier-1: 71% (36 cases)  | INSUFFICIENT_FUNDS:   52%       |
| Tier-2: 29% (15 cases)  | BANK_TECHNICAL:       88%       |
|                         | MANDATE_PAUSED:       40%       |
|                         | AFA_REQUIRED:         67%       |
+-------------------------+----------------------------------+
| RECENT MANDATES                         | HUMAN REVIEW (4) |
| MAND-001 SCHEDULED  Tier-1  9,800      | MAND-012 EMI     |
| MAND-002 ESCALATED  Tier-1  45,000     | MAND-023 Bounce  |
| MAND-003 LINK SENT  Tier-2  12,000     |                  |
+------------------------------------------------------------+
```

---

## 10. Information Architecture

```
Aegis System
|-- /api                            (Backend REST API)
|   |-- /v1/recovery/batch          POST - upload and process a batch of failed mandates
|   |-- /v1/mandates/{id}           GET - get full decision trail for a mandate
|   |-- /v1/metrics                 GET - summary metrics (recovery rate, tier split, violations)
|   |-- /v1/audit                   GET - paginated audit log
|   `-- /webhooks/razorpay          POST - receive Razorpay subscription webhooks
|-- /dashboard                      (Frontend React App)
|   |-- /                           Summary dashboard (Rs. recovered front-page)
|   |-- /batch                      Batch upload and results
|   |-- /mandates                   Mandate list with detail drawer
|   `-- /audit                      Audit log viewer
|-- /config
|   `-- compliance_config.yaml      Compliance thresholds and limits
|-- /data
|   `-- synthetic/                  Mandate event generator + held-out set
`-- /tests
    |-- unit/
    `-- integration/
```

---

## 11. UX & Interaction Design

### Design Aesthetic
- **Financial operations aesthetic:** Clean, data-dense, professional. Not playful.
- **India-first:** Currency in Rs. (not $); dates in IST; category names match NPCI terminology
- **Status colors:** Green = recovered/executed, Amber = escalated/human-review, Red = failed/violation-blocked, Blue = mocked/notification-sent

### Key Interaction Patterns

**1. Batch Upload Flow**
Drag-and-drop CSV or click-to-upload. After upload, a progress bar shows:
1. Parsing CSV (instant)
2. Running Tier-1 (instant)
3. Running Tier-2 for N ambiguous cases (shows progress per case)
4. Applying compliance gate (instant)
5. Executing actions (varies)

**2. The Compliance Violation Moment (Demo-Critical)**
When a compliance violation is caught, the UI renders a distinctive "Compliance Override" card:
```
[COMPLIANCE OVERRIDE]
Mandate: MAND-042 (Loan EMI, 2nd hard decline)
Claude (Tier-2) proposed: RETRY_AFTER_BACKOFF
Compliance Gate: REJECTED
Rule triggered: non_revocable_mandate_no_auto_retry
Final action: ESCALATE_TO_HUMAN
[View full audit entry]
```

**3. Hinglish Message Preview**
For each mandate where a Hinglish message is drafted, the dashboard shows a preview card with the message text, the channel it would be sent on (WhatsApp/SMS — mocked), and a "Would Send" label (never "Sent").

**4. Held-Out Metrics Tab**
A separate tab showing evaluation metrics on the held-out slice:
- Recovery rate per category (table)
- Tier-1 vs. Tier-2 accuracy (confusion matrix optional)
- False escalation rate
- Compliance violations caught

---

## 12. System Architecture

### High-Level Architecture

```
[EXTERNAL INPUT]
  CSV or JSON batch of failed/at-risk mandate events
  (NPCI/bank-style return codes, ~14% realistic bounce-rate distribution)
         |
         | POST /api/v1/recovery/batch
         v
[AGENTGUARD Aegis SERVICE]

  TIER 1: Deterministic Rule Engine
  decline-code lookup table (the 6 categories)
  resolves ~65-75% of the batch in milliseconds
         |
  Only ambiguous/composite/unseen codes fall through
         |
  TIER 2: Claude Reasoning Agent (structured output ONLY)
  in:  {mandate_id, decline_code, customer_features, history}
  out: {action: <fixed allow-list>, message_hinglish: str,
        rationale: str, confidence: float}
  -- cannot invent an action outside the allow-list
         |
  COMPLIANCE GATE (deterministic, non-LLM, cannot be bypassed)
  enforces: max_retry_attempts, 24h pre-debit notice,
            AFA-threshold routing, non-revocable -> escalation-only
  any violation: REJECTED here, logged as "blocked"
         |
  ACTION EXECUTOR
  Razorpay TEST-MODE Subscriptions API (pause/resume/cancel)
  + Payment Links API (new-mandate / UPI-intent links)
  + mock notification stub (logs, does not send)
         |
  APPEND-ONLY AUDIT LOG
  {mandate_id, timestamp, tier_that_decided, reason_code,
   alternatives_considered, compliance_check_result, outcome}
         |
  DASHBOARD
  recovery rate, Rs. recovered / at risk,
  exceptions, compliance-violations-caught,
  Tier-1-vs-Tier-2 split
```

### Component Responsibilities

| Component | Responsibility | LLM Used? |
|---|---|---|
| Event Ingester | CSV/JSON parsing, schema validation | No |
| Tier-1 Rule Engine | Decline code lookup, deterministic action | No |
| Tier-2 Groq Agent | Ambiguous case reasoning, Hinglish drafting | Yes (Groq — Llama-3.3-70b-versatile) |
| Compliance Gate | Unconditional rule enforcement | No |
| Action Executor | Razorpay API calls + mock stubs | No |
| Audit Log | Append-only decision record | No |
| Dashboard | Recovery metrics visualization | No |

---

## 13. Data Architecture

### Database: PostgreSQL (or SQLite for hackathon speed)

### Table: mandate_events
```sql
CREATE TABLE mandate_events (
  mandate_id              UUID PRIMARY KEY,
  customer_id             VARCHAR(100) NOT NULL,
  amount                  INT NOT NULL,            -- INR, integer
  mandate_type            VARCHAR(20) NOT NULL,    -- UPI_AUTOPAY | ENACH
  decline_code            VARCHAR(50) NOT NULL,
  days_since_salary_credit INT NOT NULL,
  prior_bounce_count      INT NOT NULL DEFAULT 0,
  is_revocable            BOOLEAN NOT NULL DEFAULT TRUE,
  attempt_number          INT NOT NULL DEFAULT 1,
  event_timestamp         TIMESTAMPTZ NOT NULL,
  batch_id                UUID NOT NULL,           -- Which upload batch
  is_held_out             BOOLEAN NOT NULL DEFAULT FALSE,
  correct_action          VARCHAR(50)              -- Ground-truth label (evaluation only)
);
```

### Table: recovery_decisions
```sql
CREATE TABLE recovery_decisions (
  decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id          UUID NOT NULL REFERENCES mandate_events(mandate_id),
  tier_that_decided   SMALLINT NOT NULL,           -- 1 or 2
  proposed_action     VARCHAR(50) NOT NULL,
  compliance_approved BOOLEAN NOT NULL,
  violation_blocked   BOOLEAN NOT NULL DEFAULT FALSE,
  violation_rule      VARCHAR(100),
  final_action        VARCHAR(50) NOT NULL,
  outcome             VARCHAR(20) NOT NULL,        -- executed|mocked|escalated|failed
  rationale           TEXT,
  confidence          DECIMAL(3,2),
  hinglish_message    TEXT,
  alternatives        JSONB,
  razorpay_response   JSONB,
  decided_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Table: audit_log (append-only)
```sql
CREATE TABLE audit_log (
  entry_id        BIGSERIAL PRIMARY KEY,
  mandate_id      UUID NOT NULL,
  decision_id     UUID NOT NULL,
  timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload         JSONB NOT NULL
);
REVOKE UPDATE, DELETE ON audit_log FROM Aegis_app;
```

### Table: human_review_queue
```sql
CREATE TABLE human_review_queue (
  review_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id      UUID NOT NULL REFERENCES mandate_events(mandate_id),
  reason          VARCHAR(200) NOT NULL,
  compliance_rule VARCHAR(100),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at     TIMESTAMPTZ,
  resolved_by     VARCHAR(100)
);
```

### Held-Out Evaluation Schema
```python
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
```

---

## 14. AI/ML Architecture

### LLM Provider: Groq API (Free Tier)

Groq is used instead of Anthropic. Groq provides free API access with extremely low inference latency. The integration pattern (chat completions + function calling) is OpenAI-compatible, making the groq SDK a drop-in replacement.

**Used for exactly two tasks:**
1. **Ambiguous case reasoning (Tier-2):** Select an action from the fixed allow-list based on the mandate context and customer history. Produce a Hinglish customer message and a rationale.
2. **Structured output only:** The model's output is always a function call filling the `propose_recovery_action` schema. Free-text responses are rejected by Pydantic validation.

**Explicitly NOT used for:**
- Tier-1 classification (this is a lookup table)
- Compliance gate decisions (unconditional rules)
- Any action execution
- Any financial risk judgment that has a deterministic rule equivalent

### Recommended Groq Models for Aegis

| Use Case | Model | Reason |
|---|---|---|
| **Tier-2 complex reasoning (primary)** | `llama-3.3-70b-versatile` | Best reasoning accuracy for ambiguous composite cases; most reliable structured output; handles nuanced mandate context |
| **Tier-2 high-volume batches (speed)** | `llama-3.1-8b-instant` | ~5× faster than 70B; use when batch size > 100 and speed matters more than marginal accuracy on ambiguous cases |
| **Hinglish message drafting** | `llama-3.3-70b-versatile` | Better cultural fluency and code-switching quality for Hindi-English mix |
| **Fallback if rate-limited** | `mixtral-8x7b-32768` | Good function calling, 32k context window fits full mandate history |

> **Tier-2 model strategy:** For a hackathon demo batch of 50–200 records, always use `llama-3.3-70b-versatile`. The free Groq tier handles this comfortably within rate limits. If you scale to 1,000+ records, switch ambiguous cases to `llama-3.1-8b-instant` for the Hinglish drafting step and reserve 70B for the action-selection step only.

### Groq Client Integration for Tier-2
```python
from groq import Groq
import os, json

client = Groq(api_key=os.environ["GROQ_API_KEY"])

async def tier2_reason(event: MandateEvent) -> Tier2Result:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(allowed_actions=ALLOWED_ACTIONS)},
            {"role": "user", "content": format_mandate_context(event)}
        ],
        tools=[PROPOSE_RECOVERY_TOOL],
        tool_choice={"type": "function", "function": {"name": "propose_recovery_action"}},
        temperature=0.2,    # Slight randomness for Hinglish message variety
        max_tokens=512,
    )
    tool_call = response.choices[0].message.tool_calls[0]
    result_dict = json.loads(tool_call.function.arguments)
    # Pydantic validation — rejects any action outside ALLOWED_ACTIONS
    return Tier2Result(**result_dict)
```

### Prompt Architecture for Tier-2
```python
SYSTEM_PROMPT = """
You are a mandate recovery specialist for an Indian NBFC/subscription business.
You analyze failed UPI Autopay and e-NACH mandate cases and propose recovery actions.

IMPORTANT CONSTRAINTS:
1. You MUST call the propose_recovery_action function. Do not respond in plain text.
2. You can ONLY propose actions from this list: {allowed_actions}
3. The action you propose will pass through a compliance gate before execution.
   Do not worry about compliance — just propose the best customer-centric action.
4. Draft the Hinglish message in a warm, loss-aversion framing.
   Example: "Aapka subscription abhi bhi active hai — sirf ek step aur!"
5. If you are not confident (confidence < 0.6), set action to ESCALATE_TO_HUMAN.
Always respond using the function call — never in plain text.
"""

PROPOSE_RECOVERY_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_recovery_action",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ALLOWED_ACTIONS},
                "message_hinglish": {"type": "string"},
                "rationale": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "alternatives_considered": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["action", "message_hinglish", "rationale", "confidence"]
        }
    }
}
```

### Why No More Than 30% Should Hit Tier-2
- If the rule engine is comprehensive for the six taxonomy categories, it should resolve ~65–75% of the realistic synthetic batch
- Routing more than 30% to Groq signals that the rule engine has gaps — this is a debugging signal, not a feature
- Track the Tier-1 vs. Tier-2 split on the dashboard and keep it visible; judges will notice

### Optional Stretch — Predictive At-Risk Scorer
If time allows (3+ days of spare time after MVP dashboard works):
```python
from sklearn.linear_model import LogisticRegression

def build_atrisk_classifier(training_data: list[MandateEvent]) -> LogisticRegression:
    """
    Predicts probability of mandate failure BEFORE it fails.
    Features: days_since_salary_credit, prior_bounce_count,
              amount vs. AFA_threshold ratio, attempt_number
    This separates 'reactive dunning bot' from genuinely predictive.
    """
    X = extract_features(training_data)
    y = [1 if e.decline_code != "SUCCESS" else 0 for e in training_data]
    model = LogisticRegression()
    model.fit(X, y)
    return model
```

This is the single best use of spare time. It separates the project from "reactive dunning tool" to "predictive mandate intelligence."

### Model Selection Summary
- **Primary (Tier-2 reasoning):** `llama-3.3-70b-versatile` — best accuracy, supports function calling, excellent Hinglish quality
- **Speed alternative (large batches):** `llama-3.1-8b-instant` — ~5× faster, use when batch > 100 records
- **Fallback:** `mixtral-8x7b-32768` — long context, solid function calling
- All calls use `temperature=0.2` for Hinglish variety; `temperature=0` for action selection if using two-step

---

## 15. APIs & Integrations

### Internal REST API

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/recovery/batch | Upload CSV of failed mandates; returns batch_id |
| GET | /api/v1/recovery/batch/{batch_id} | Get results of a batch run |
| GET | /api/v1/mandates/{id} | Full decision trail for a single mandate |
| GET | /api/v1/metrics | Summary metrics (recovery rate, tier split, violations) |
| GET | /api/v1/audit | Paginated audit log |
| GET | /api/v1/human-review | Human review queue |
| POST | /webhooks/razorpay | Receive Razorpay subscription webhooks |

### Razorpay Subscriptions API

**Create Demo Subscriptions (setup only):**
```
POST https://api.razorpay.com/v1/subscriptions
{
  "plan_id": "plan_XXX",
  "total_count": 12,
  "customer_notify": 0,
  "notes": { "customer_id": "CUST-001" }
}
```

**Resume Subscription (for RETRY_AFTER_BACKOFF):**
```
POST https://api.razorpay.com/v1/subscriptions/{id}/resume
```

**Create Payment Link (for UPI intent push / mandate renewal):**
```
POST https://api.razorpay.com/v1/payment_links
{
  "amount": 1800000,      // Paise
  "currency": "INR",
  "description": "EMI Recovery - MAND-042",
  "upi_link": true        // UPI-intent link for AFA-required cases
}
```

**Webhook Events:**
| Event | Action |
|---|---|
| subscription.pending | Fires when charge fails and subscription moves active->pending |
| subscription.charged | Fires on successful charge/retry |
| payment.failed | Update mandate event status; trigger recovery pipeline |
| subscription.activated | Confirm recovery success |

**Test Mode Trick:** Use Razorpay's dashboard "Test Subscriptions charge simulator" to manually trigger subscription charge as success or failure on demand. Do NOT wait for real billing-cycle timers during the demo.

### Mock Notification Stub

```python
class MockNotificationService:
    """
    Simulates WhatsApp/SMS/voice notification.
    Judges care about the decision logic, not a WhatsApp API key.
    """
    def __init__(self, log_file: str = "notification_log.jsonl"):
        self.log_file = log_file

    def send(self, customer_id: str, message: str, channel: str) -> dict:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "customer_id": customer_id,
            "channel": channel,
            "message": message,
            "status": "MOCKED -- would send in production"
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"[MOCK] would send via {channel} to {customer_id}: {message[:50]}...")
        return entry
```

---

## 16. Security & Compliance

### Compliance Architecture

The compliance gate is the primary compliance mechanism. It enforces:

1. **Max Retry Cap (Config-Driven, Never Learned):**
   - UPI Autopay: max 3 automatic retries
   - e-NACH: max 2 automatic retries (higher bounce fee)
   - Any proposed retry action exceeding this cap is rejected

2. **24-Hour Pre-Debit Notice Rule (RBI Mandate):**
   - If a mandate was paused due to the 24h pre-debit notification, no retry is permitted
   - Only SEND_HINGLISH_NUDGE (customer communication) or ESCALATE_TO_HUMAN are allowed

3. **AFA Threshold Routing (NPCI Rule):**
   - General: Rs. 15,000 — silent auto-debit blocked above this
   - SIP/Insurance/Credit Cards: Rs. 1,00,000
   - Any amount above threshold must route to SEND_UPI_INTENT_PUSH — never a silent retry

4. **Non-Revocable Mandate Hard Decline:**
   - Loan EMIs, certain insurance mandates
   - If is_revocable=False and decline_code=NON_REVOCABLE_HARD_DECLINE: ESCALATE_TO_HUMAN, unconditionally
   - Zero exceptions. Not configurable.

### Data Security
- All mandate data is synthetic — no real PII, no real bank data
- Audit log is append-only at the database role level (REVOKE UPDATE, DELETE)
- API keys in environment variables, never in code
- All database connections use TLS

### Proving Compliance in the Panel Round
The answer to "how do you know the compliance gate can't be bypassed?" is:
1. It is a pure function — same inputs always produce the same output
2. It has unit tests for every rule in isolation
3. It is structurally separate from Tier-1 and Tier-2 — it receives a proposed action, it does not generate one
4. Its output is the final_action — nothing downstream reads the proposed_action directly

---

## 17. Cost & Scalability Considerations

### Groq API Costs (Demo Scale)
- **Free tier:** Groq's free API tier provides generous rate limits (approx. 14,400 requests/day on llama-3.3-70b-versatile, 30 requests/min)
- Tier-2 cases: 25–35% of 50–200 records = 12–70 cases — **$0.00 on the free tier**
- Total for a full demo batch of 200 records: **$0.00 total**
- Rate limit risk: 30 req/min on 70B; 15–70 Tier-2 calls across a batch demo is well within limit
- If rate-limited: switch Tier-2 to `llama-3.1-8b-instant` (60 req/min) as a fallback

### Database Size (Demo Scale)
- 1,000 mandate events + decisions + audit: ~5MB
- Easily handled by a single SQLite file or Postgres instance

### Scalability Architecture (Post-MVP)
- Tier-1 is embarrassingly parallelizable: process records in parallel with no shared state
- Tier-2 is the bottleneck: LLM calls are sequential per case (parallelizable with async)
- The compliance gate is a pure function: zero shared state, infinitely parallelizable
- The audit log is append-only: naturally shardable by batch_id or timestamp

---

## 18. Technical Stack & Infrastructure

### Backend
- **Language:** Python 3.12+
- **Framework:** FastAPI (async)
- **LLM Client:** `groq` Python SDK (`pip install groq`) — OpenAI-compatible interface
- **Razorpay Client:** `razorpay` Python SDK
- **Database ORM:** SQLAlchemy 2.0 (async) — or raw SQL if time is tight
- **Validation:** Pydantic v2
- **Config:** PyYAML for compliance_config.yaml
- **Synthetic data:** Python + faker

### Database
- **Primary:** SQLite (fast to set up) or PostgreSQL (more production-realistic)
- **Append-only enforcement:** REVOKE UPDATE, DELETE on audit_log in Postgres; in SQLite, enforce in application code

### Frontend
- **Framework:** React 18 with TypeScript (preferred) or Streamlit (faster to build)
- **Charts:** Recharts or Chart.js
- **File upload:** react-dropzone for CSV upload
- **Alternative:** If solo developer, use Streamlit — the metrics matter more than the polish

### Infrastructure
- **Cloud:** AWS EC2 (t3.small or t3.medium, Ubuntu 22.04 LTS)
- **CI/CD:** GitHub Actions (separate repo, separate EC2 from AgentGuard)
- **Reverse Proxy:** Nginx (routes ports, handles SSL termination)
- **SSL:** Let's Encrypt via certbot (free)
- **Process Manager:** Docker Compose on EC2
- **Environment:** .env file on EC2 (never committed to repo)

---

## 19. State Management & Data Flow

### Batch Lifecycle State Machine

```
[UPLOADED]      -> CSV received and parsed
      |
[TIER1_RUNNING] -> All records processed by rule engine simultaneously
      |
[TIER2_RUNNING] -> Ambiguous cases queued and processed by Groq (Llama)
      |
[GATE_CHECKING] -> All proposed actions pass through compliance gate
      |
[EXECUTING]     -> Approved actions execute against Razorpay / mock
      |
[COMPLETE]      -> All records have a final_action and outcome
```

### Per-Mandate State Machine

```
[RECEIVED]
      |
 Tier-1 rule
      |
[TIER1_RESOLVED] -> compliance gate -> [EXECUTED | ESCALATED | MOCKED]
      |
 (if ambiguous)
      |
[TIER2_PENDING]
      |
 Claude call
      |
[TIER2_RESOLVED] -> compliance gate -> [EXECUTED | COMPLIANCE_BLOCKED | ESCALATED | MOCKED]
```

---

## 20. Backend Architecture

### Project Structure

```
Aegis/
|-- api/
|   |-- main.py
|   |-- routes/
|   |   |-- recovery.py       # POST /v1/recovery/batch
|   |   |-- mandates.py       # GET /v1/mandates/{id}
|   |   |-- metrics.py        # GET /v1/metrics
|   |   |-- audit.py          # GET /v1/audit
|   |   `-- webhooks.py       # POST /webhooks/razorpay
|-- core/
|   |-- tier1_engine.py       # Deterministic rule lookup
|   |-- tier2_agent.py        # Groq (Llama) structured output
|   |-- compliance_gate.py    # Unconditional compliance enforcement
|   `-- action_executor.py    # Razorpay + mock stub dispatch
|-- services/
|   |-- razorpay_client.py
|   `-- mock_notification.py
|-- audit/
|   `-- log.py                # Append-only audit write
|-- models/
|   |-- mandate_event.py      # Pydantic model
|   |-- recovery_decision.py  # Pydantic model
|   `-- db.py                 # SQLAlchemy models
|-- config/
|   `-- loader.py             # compliance_config.yaml loader
|-- synthetic/
|   |-- generator.py          # Mandate event generator
|   |-- held_out.py           # Held-out set management
|   `-- evaluator.py          # Held-out evaluation metrics
|-- tests/
|   |-- unit/
|   |   |-- test_tier1.py
|   |   |-- test_compliance_gate.py
|   |   `-- test_audit.py
|   `-- integration/
|       `-- test_batch_pipeline.py
|-- compliance_config.yaml
|-- .env.example
|-- docker-compose.yml
`-- requirements.txt
```

### Batch Processing Orchestrator

```python
async def process_batch(events: list[MandateEvent]) -> BatchResult:
    results = []
    for event in events:
        # Tier 1
        tier1_result = tier1_engine.classify(event)

        if tier1_result.is_ambiguous:
            # Tier 2
            tier2_result = await tier2_agent.reason(event)
            proposed_action = tier2_result.action
            tier_decided = 2
        else:
            proposed_action = tier1_result.action
            tier_decided = 1

        # Compliance Gate (always runs)
        compliance_result = compliance_gate.check(event, proposed_action)
        final_action = compliance_result.final_action

        # Execute
        outcome = await action_executor.execute(event, final_action, tier2_result.message_hinglish if tier_decided == 2 else None)

        # Audit
        audit_log.append(event, proposed_action, compliance_result, final_action, outcome, tier_decided)

        results.append(RecoveryDecision(
            mandate_id=event.mandate_id,
            tier_that_decided=tier_decided,
            proposed_action=proposed_action,
            compliance_result=compliance_result,
            final_action=final_action,
            outcome=outcome,
        ))

    return BatchResult(decisions=results, metrics=compute_metrics(results))
```

---

## 21. Frontend Architecture

### React App Structure

```
dashboard/
`-- src/
    |-- components/
    |   |-- MetricCards.tsx          # Rs. recovered, recovery %, violations
    |   |-- TierSplitChart.tsx       # Tier-1 vs Tier-2 donut chart
    |   |-- RecoveryByCategoryTable.tsx
    |   |-- MandateList.tsx          # Scrollable mandate table
    |   |-- MandateDetailDrawer.tsx  # Full decision trail
    |   |-- ComplianceOverrideCard.tsx  # The key demo component
    |   |-- HinglishMessagePreview.tsx
    |   |-- HumanReviewQueue.tsx
    |   `-- BatchUploader.tsx        # CSV drag-and-drop
    |-- pages/
    |   |-- Dashboard.tsx
    |   |-- Batch.tsx
    |   `-- Audit.tsx
    |-- api/
    |   `-- Aegis.ts
    `-- App.tsx
```

---

## 22. Testing Strategy

### Test Pyramid

```
        [E2E Tests] (full batch pipeline, held-out evaluation)
    [Integration Tests] (API endpoints, Razorpay mock, audit log)
[Unit Tests] (each rule, each gate check, Tier-2 output validation)
```

### Unit Tests — Tier-1 Rule Engine

```python
def test_insufficient_funds_scheduled():
    event = MandateEvent(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=3)
    result = tier1_engine.classify(event)
    assert result.action == "SCHEDULE_POST_SALARY"
    assert not result.is_ambiguous

def test_insufficient_funds_high_bounce_escalated():
    event = MandateEvent(decline_code="INSUFFICIENT_FUNDS", prior_bounce_count=4)
    result = tier1_engine.classify(event)
    assert result.action == "ESCALATE_TO_HUMAN"

def test_afa_required_routes_to_intent_push():
    event = MandateEvent(decline_code="AFA_REQUIRED", amount=16000)
    result = tier1_engine.classify(event)
    assert result.action == "SEND_UPI_INTENT_PUSH"

def test_non_revocable_escalated():
    event = MandateEvent(decline_code="NON_REVOCABLE_HARD_DECLINE", is_revocable=False)
    result = tier1_engine.classify(event)
    assert result.action == "ESCALATE_TO_HUMAN"

def test_bank_technical_retried():
    event = MandateEvent(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=1, mandate_type="UPI_AUTOPAY")
    result = tier1_engine.classify(event)
    assert result.action == "RETRY_AFTER_BACKOFF"
```

### Unit Tests — Compliance Gate (Critical)

```python
def test_non_revocable_retry_blocked():
    event = MandateEvent(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.final_action == "ESCALATE_TO_HUMAN"
    assert result.violation_blocked == True
    assert result.violation_rule == "non_revocable_mandate_no_auto_retry"

def test_afa_silent_retry_blocked():
    event = MandateEvent(amount=16000, decline_code="AFA_REQUIRED")
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.final_action == "SEND_UPI_INTENT_PUSH"
    assert result.violation_rule.startswith("afa_threshold_requires_intent_push")

def test_max_retries_exceeded_blocked():
    event = MandateEvent(mandate_type="ENACH", attempt_number=2, decline_code="BANK_TECHNICAL_DECLINE")
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.violation_blocked == True

def test_compliant_action_approved():
    event = MandateEvent(mandate_type="UPI_AUTOPAY", attempt_number=1, is_revocable=True, amount=5000)
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert result.approved
    assert result.final_action == "RETRY_AFTER_BACKOFF"
```

### Integration Tests
- Full pipeline test: run a 50-record batch, verify tier split is 65–75% Tier-1
- Compliance integration: inject a deliberate non-compliant Tier-2 output; verify gate catches it
- Held-out evaluation: run evaluator on held-out set; verify recovery_rate >= target per category
- Audit log integration: verify every record produces exactly one audit entry

### Evaluation on Held-Out Set (Required before Demo Recording)
```python
def evaluate_held_out_set():
    held_out = load_held_out_events()
    results = process_batch(held_out)
    correct = sum(1 for r, e in zip(results.decisions, held_out)
                  if r.final_action == e.correct_action)
    print(f"Accuracy: {correct / len(held_out):.1%}")
    print(f"Compliance violations executed: {results.metrics.compliance_violations_executed}")
    assert results.metrics.compliance_violations_executed == 0, "NO compliance violation should reach execution!"
```

---

## 23. Observability & Monitoring

### Logging
- Structured JSON logs for every Tier-1 decision, Tier-2 call, compliance gate check, and action execution
- Log fields: mandate_id, tier, proposed_action, compliance_approved, final_action, outcome, latency_ms

### Dashboard Metrics
- Rs. recovered vs. Rs. at risk (primary KPI)
- Recovery rate by category (on held-out set)
- Tier-1 vs. Tier-2 split (percentage)
- Compliance violations caught (> 0 proves the gate works) vs. executed (must = 0)
- Tier-1 latency P95, Tier-2 latency P95

### Alert Conditions (Post-MVP)
- Compliance gate catch rate drops to 0 on a batch with known violations -> CRITICAL (gate may be bypassed)
- Tier-2 rate exceeds 40% on a batch -> WARNING (Tier-1 rule engine may have gaps)

---

## 24. Deployment Strategy

### Overview
Aegis is deployed as a standalone project on a dedicated AWS EC2 instance (separate from AgentGuard), with GitHub Actions handling CI/CD from its own GitHub repo. Nginx runs as a reverse proxy in front of FastAPI and serves the React/Streamlit dashboard. PostgreSQL (or SQLite) runs on the same instance.

```
[GitHub Repo: Aegis]
         |
   push to main branch
         |
   GitHub Actions workflow
         |
   SSH into EC2 + docker compose up --build
         |
[AWS EC2 Instance (Aegis)]
  Nginx (:80/:443)
    |-- /api      --> FastAPI (:8001)
    |-- /         --> React build or Streamlit
  PostgreSQL/SQLite (internal only)
  Docker Compose manages all services
```

> **Note:** Aegis runs on port 8001 internally (to avoid conflict if testing both projects on the same machine during development). On EC2, it has its own dedicated instance, so it uses 8000 externally behind Nginx.

---

### Step 1 — EC2 Instance Setup (One-time)

```bash
# 1. Launch EC2: Ubuntu 22.04 LTS, t3.small minimum, t3.medium recommended
#    (Separate instance from AgentGuard)
# 2. Security Group inbound rules:
#    - Port 22  (SSH)   — your IP only
#    - Port 80  (HTTP)  — 0.0.0.0/0
#    - Port 443 (HTTPS) — 0.0.0.0/0
# 3. Assign an Elastic IP to the instance

# SSH into the instance
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Install Docker + Docker Compose + Nginx
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git nginx certbot python3-certbot-nginx
sudo usermod -aG docker ubuntu
newgrp docker

# Create app directory
mkdir -p /home/ubuntu/Aegis
```

---

### Step 2 — Nginx Configuration

```nginx
# /etc/nginx/sites-available/Aegis
server {
    listen 80;
    server_name Aegis.yourdomain.com;  # Replace with your domain or EC2 IP

    # API — FastAPI backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Razorpay webhooks
    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # React dashboard — serve static build
    # If using Streamlit instead, proxy to port 8501:
    # location / { proxy_pass http://127.0.0.1:8501; }
    location / {
        root /home/ubuntu/Aegis/dashboard/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
# Enable and test
sudo ln -s /etc/nginx/sites-available/Aegis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL via Let's Encrypt
sudo certbot --nginx -d Aegis.yourdomain.com
```

---

### Step 3 — Docker Compose on EC2

```yaml
# docker-compose.yml (committed to repo, no secrets)
version: '3.8'
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env           # .env lives on EC2, never in repo
    volumes:
      - ./compliance_config.yaml:/app/compliance_config.yaml
      - ./data:/app/data     # Synthetic data + held-out fixtures
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: Aegis
      POSTGRES_USER: Aegis
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U Aegis"]
      interval: 10s
      retries: 5
    restart: unless-stopped

volumes:
  pgdata:
```

---

### Step 4 — .env File on EC2 (Never Commit This)

Create this file at `/home/ubuntu/Aegis/.env` directly on the EC2 instance:

```bash
# /home/ubuntu/Aegis/.env
# ============================================================
# Aegis — Environment Configuration
# DO NOT commit this file. Add .env to .gitignore.
# ============================================================

# ----- Groq API (LLM — Tier-2 Reasoning & Hinglish Drafting) -----
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Primary model for Tier-2 reasoning (best accuracy for ambiguous cases)
GROQ_MODEL_TIER2=llama-3.3-70b-versatile
# Speed alternative for large batches (>100 ambiguous cases)
GROQ_MODEL_TIER2_FAST=llama-3.1-8b-instant
# Fallback model if primary is rate-limited
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768

# ----- Razorpay (Test Mode ONLY) -----
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Note: This is a SEPARATE webhook endpoint from AgentGuard
# Register in Razorpay dashboard: https://Aegis.yourdomain.com/webhooks/razorpay
# Events: payment.failed, subscription.pending, subscription.charged, subscription.activated

# ----- PostgreSQL Database -----
DB_PASSWORD=your_strong_random_password_here
DATABASE_URL=postgresql://Aegis:${DB_PASSWORD}@db:5432/Aegis

# ----- Application Security -----
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
# Must be DIFFERENT from AgentGuard's SECRET_KEY
SECRET_KEY=your_64_char_hex_secret_here_different_from_agentguard

# ----- CORS & Hosting -----
ALLOWED_ORIGINS=https://Aegis.yourdomain.com,http://localhost:3000
APP_HOST=Aegis.yourdomain.com

# ----- Compliance Configuration -----
# These are defaults; the real values live in compliance_config.yaml
AFA_THRESHOLD_GENERAL=15000
AFA_THRESHOLD_SIP_INSURANCE=100000

# ----- App Behaviour -----
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

### Step 5 — .env.example (Commit This to Repo)

```bash
# .env.example — committed to repo as a template
# Copy to .env and fill in real values on your EC2 instance

GROQ_API_KEY=
GROQ_MODEL_TIER2=llama-3.3-70b-versatile
GROQ_MODEL_TIER2_FAST=llama-3.1-8b-instant
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

DB_PASSWORD=
DATABASE_URL=postgresql://Aegis:changeme@db:5432/Aegis

SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:3000
APP_HOST=localhost

AFA_THRESHOLD_GENERAL=15000
AFA_THRESHOLD_SIP_INSURANCE=100000

ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

---

### Step 6 — GitHub Actions CI/CD Workflow

Create this file at `.github/workflows/deploy.yml` in the Aegis repo:

```yaml
name: Deploy Aegis to EC2

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v
        env:
          # Unit tests use mock LLM — no real API key needed
          GROQ_API_KEY: test_key_not_used_in_unit_tests
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test_secret_key_32_chars_minimum
      - name: Run compliance gate tests specifically
        run: pytest tests/unit/test_compliance_gate.py -v --tb=short
        env:
          GROQ_API_KEY: test_key_not_used_in_unit_tests
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test_secret_key_32_chars_minimum

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Build React dashboard
        working-directory: ./dashboard
        run: |
          npm ci
          npm run build

      - name: Copy files to EC2 via rsync
        uses: burnett01/rsync-deployments@7.0.1
        with:
          switches: -avzr --delete --exclude='.env' --exclude='node_modules' --exclude='__pycache__' --exclude='data/held_out*'
          path: ./
          remote_path: /home/ubuntu/Aegis
          remote_host: ${{ secrets.EC2_HOST }}
          remote_user: ${{ secrets.EC2_USERNAME }}
          remote_key: ${{ secrets.EC2_SSH_PRIVATE_KEY }}

      - name: Deploy on EC2
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USERNAME }}
          key: ${{ secrets.EC2_SSH_PRIVATE_KEY }}
          script: |
            cd /home/ubuntu/Aegis

            # Run DB migrations (if using Alembic)
            docker compose run --rm api alembic upgrade head

            # Restart services
            docker compose up --build -d

            # Reload Nginx
            sudo systemctl reload nginx

            echo "Aegis deployed successfully"
```

### GitHub Repository Secrets (Settings -> Secrets -> Actions)

| Secret Name | Value |
|---|---|
| `EC2_HOST` | Aegis's EC2 Elastic IP or domain |
| `EC2_SSH_PRIVATE_KEY` | Full contents of the EC2 .pem key file |
| `EC2_USERNAME` | `ubuntu` (Ubuntu AMI) |

> All application secrets (GROQ_API_KEY, RAZORPAY_KEY_SECRET, etc.) are stored in `.env` **directly on the EC2 instance**. The rsync step uses `--exclude='.env'` so the live .env is never overwritten by CI/CD.

> The rsync step also excludes `data/held_out*` to protect the held-out evaluation set from being overwritten by any generated data during development.

---

### Deployment Checklist (First-Time Setup)

- [ ] EC2 instance launched (Ubuntu 22.04, t3.small+, **separate from AgentGuard**), Elastic IP assigned
- [ ] Security groups open: ports 22, 80, 443
- [ ] Docker + Docker Compose + Nginx + certbot installed on EC2
- [ ] `/home/ubuntu/Aegis/.env` created with all real values
- [ ] `compliance_config.yaml` reviewed and committed to repo
- [ ] Nginx config created and enabled at `/etc/nginx/sites-available/Aegis`
- [ ] SSL certificate obtained via certbot
- [ ] Razorpay webhook URL registered: `https://Aegis.yourdomain.com/webhooks/razorpay` (separate from AgentGuard webhook)
- [ ] Razorpay: at least one test Plan + Subscription created for the charge simulator
- [ ] GitHub repo secrets set: `EC2_HOST`, `EC2_SSH_PRIVATE_KEY`, `EC2_USERNAME`
- [ ] Held-out set pre-generated and committed as `data/synthetic_held_out.csv` before any rule-writing begins
- [ ] First manual deploy: `docker compose up --build -d` on EC2
- [ ] Push to `main` branch and verify GitHub Actions workflow passes, compliance gate tests all green

---

## 25. Engineering Constraints

| Constraint | Value | Reason |
|---|---|---|
| Timeline | 13 build days | MVP delivery |
| Failure categories modeled | Exactly 6 (the taxonomy) | Depth over breadth |
| LLM on compliance decisions | Not permitted | Compliance gate is unconditional deterministic code |
| Tier-2 (LLM) volume | Must not exceed ~30% of the batch | If more, Tier-1 rule engine needs improvement |
| Bandit/RL optimizer | Not in MVP | No real convergence on synthetic data |
| Real WhatsApp/telephony | Not in MVP | Mock stub is expected and sufficient |
| Real customer PII | Not permitted | Synthetic data only |
| Live money | Not permitted | Razorpay test-mode only |

---

## 26. Performance Requirements

| Operation | Target Latency (P95) |
|---|---|
| Tier-1 classification per record | < 5ms |
| Tier-2 Groq call per case | < 1,000ms |
| Compliance gate check per record | < 5ms |
| Razorpay API call | < 1,000ms |
| Full batch of 50 records | < 30s |
| Dashboard page load | < 2,000ms |
| Audit log write per record | < 20ms |

---

## 27. Success Metrics & KPIs

| Metric | Target | How to Measure |
|---|---|---|
| Recovery rate on held-out batch | Report honestly by category | Run evaluator on the held-out set |
| Tier-1 resolution rate | 65-75% | Count records resolved without Tier-2 |
| Compliance violations caught | > 0 | Proves the gate works; log and display |
| Compliance violations executed | 0 | Hard requirement; must be 0 |
| False escalation rate | < 15% | Cases sent to human unnecessarily |
| Tier-1 latency P95 | < 5ms | Logged per record |
| Tier-2 latency P95 | < 3,000ms | Logged per record |
| Rs. recovered / Rs. at risk | Report honestly | Dashboard front-page stat |

---

## 28. Demo Flow

**Total: 5 minutes. The compliance override moment is your headline.**

| Time | Beat | What to Show |
|---|---|---|
| 0:00-0:30 | Thesis + the Rs. number | "Indian subscription businesses lose 10-20% of recurring revenue to mandate failures no global dunning tool understands. Here's what we built." |
| 0:30-1:30 | Tier-1 live | Load 50+ synthetic failed mandates. Show Tier-1 resolving ~70% in under a second. Decline-code table visible on screen. |
| 1:30-2:30 | Tier-2 live | Show Groq (Llama-3.3-70b) reasoning through 2-3 ambiguous cases. JSON output and Hinglish message on screen. |
| 2:30-3:30 | THE MOMENT | Trigger the non-revocable EMI hard-decline case. Show it blocked by the compliance gate and escalated to human. Narrate: "Claude proposed a retry here -- our compliance gate overrode it, and that override is logged." Make this unmissable. |
| 3:30-4:30 | Dashboard | Rs. recovered / Rs. at risk, recovery rate by category, violations caught vs. violations executed (0). |
| 4:30-5:00 | Close | Why this differs from Stripe/Churnkey (India-mandate-specific), and the one thing you'd build next (the predictive at-risk scorer). |

**Critical:** Run the held-out evaluation live during the demo if possible (or show pre-computed results). Zero compliance violations executed is the clearest signal.

---

## 29. MVP Scope

### In MVP

| Feature | Status |
|---|---|
| Synthetic mandate event generator (500-1,000 records) | Core |
| Held-out evaluation set (20% slice, pre-split) | Core |
| Tier-1 deterministic rule engine (all six categories) | Core |
| Tier-2 Claude reasoning agent (structured output, fixed allow-list) | Core |
| Compliance gate (all four rules, unconditionally enforced) | Core |
| Hinglish message drafting (Claude, for MANDATE_PAUSED and AFA cases) | Core |
| Action Executor (Razorpay Subscriptions API + Payment Links API) | Core |
| Mock notification stub (WhatsApp/SMS log) | Core |
| Append-only audit log | Core |
| Dashboard (Rs. recovered, tier split, violations, mandate detail) | Core |
| Held-out evaluation metrics (honest reporting) | Required |
| Unit tests for every compliance gate rule | Required |
| BUILD_LOG.md with real failures | Required for submission |
| README + architecture diagram | Required for submission |

### Explicitly Out of MVP

| Feature | Why Cut |
|---|---|
| Bandit/survival-analysis/RL optimizer | No real convergence on synthetic data |
| Real WhatsApp/SMS/voice integration | Mock stub is sufficient and expected |
| Real customer PII | Synthetic only |
| Every NPCI/bank decline code | Six well-modeled beats twenty shallow |
| Covering NACH fee structure in pricing | Advisory context only |
| Predictive at-risk scorer (ML) | Stretch goal with 3+ days of spare time |

---

## 30. Post-MVP Roadmap

### Phase 2 — Predictive At-Risk Scoring
- Logistic regression on salary-cycle features to flag at-risk mandates before they fail
- This converts Aegis from reactive ("why did it fail?") to predictive ("who will fail next week?")
- The most impactful single next step

### Phase 3 — More Failure Categories
- Expand from 6 to 15+ decline codes based on real NPCI/bank return code data
- Add bank-specific codes (HDFC, SBI, Kotak) with known patterns

### Phase 4 — Real Notification Integration
- WhatsApp Business API for Hinglish nudge delivery
- IVR/voice call integration for high-value EMI recovery
- A/B testing of message variants

### Phase 5 — Bandit-Based Retry Optimization
- Once real data is available (not synthetic), a contextual bandit can optimize retry timing
- Features: day-of-week, time-of-day, customer salary-credit-date model, prior bounce history
- Only meaningful with weeks of real data — do NOT build this on synthetic data

### Phase 6 — Razorpay Product Integration
- Module in Razorpay's Subscription Recovery Agent product
- Dashboard integrated into Razorpay's merchant portal
- Compliance config editable from the Razorpay merchant dashboard

---

## 31. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Synthetic data looks obviously fake | Medium | Medium | Base decline-code distribution on the ~14% published bounce-rate stat; run the full batch live, don't hand-pick a "nice" one |
| Claude occasionally proposes a non-compliant action | Expected | Low | This is the entire point of the compliance gate — make sure at least one such case is visible in the demo (step 4 of §28) rather than hidden |
| Scope creep into bandit/survival modeling | Medium | High | The heuristic is defensible on its own; only touch stretch goal once MVP dashboard fully works |
| Razorpay test-mode subscription webhooks take real wall-clock time | Medium | Medium | Use the Test Subscriptions manual charge-simulator to force states on demand during the live demo |
| Tier-2 percentage exceeds 30% on the demo batch | Medium | Low | Add more specific rules to Tier-1; or accept it and explain the tradeoff honestly |
| Claude returns an action outside the allow-list | Low | Low | Pydantic schema validation rejects it; fall back to ESCALATE_TO_HUMAN |
| Compliance gate has a subtle bug that lets a violation through | Low | High | Unit test every rule; run a deliberate violation batch and assert compliance_violations_executed == 0 before recording the demo |

---

## 32. Open Questions

1. **Held-out set size:** The PRD says 20% held-out. For a 500-record dataset, that's 100 records. For a 1,000-record dataset, that's 200. **Assumption:** Generate 500 records; hold out 100 (20%).

2. **AFA threshold for e-NACH SIPs:** The PRD cites Rs. 1,00,000 for SIPs and insurance. Should this be detected from the mandate_type or a separate field? **Assumption:** Add a `product_category` field to MandateEvent (values: "subscription", "loan_emi", "sip", "insurance"); AFA threshold varies by category.

3. **Hinglish message channel:** The mock stub logs to a file. Should the dashboard show the message content for all cases, or only for cases where SEND_HINGLISH_NUDGE is the final action? **Assumption:** Show Hinglish message preview for any case where Claude drafted one, regardless of whether it was the final action.

4. **Human review queue resolution:** Is there a UI for a human to mark a review item as "resolved"? **Assumption:** Yes — a simple "Mark as Resolved" button on the human review queue row. No workflow beyond that for MVP.

5. **Batch upload format:** CSV with headers matching the MandateEvent schema, or a Razorpay-webhook-style JSON format? **Assumption:** CSV is the primary interface (simpler for the demo upload flow); JSON batch endpoint is secondary.

---

## 33. Glossary

| Term | Definition |
|---|---|
| Aegis | This system -- the two-tier failure diagnosis and recovery agent for UPI Autopay and e-NACH mandates |
| UPI Autopay | NPCI's recurring payment mechanism via UPI; zero consumer bounce fee |
| e-NACH | Electronic National Automated Clearing House; traditional recurring debit with Rs. 200-500 consumer bounce fee |
| AFA | Additional Factor of Authentication -- NPCI rule requiring explicit customer approval for auto-debits above Rs. 15,000 |
| Non-Revocable Mandate | A mandate (typically loan EMI) that cannot be legally auto-retried after a hard decline |
| 24h Pre-Debit Notice | RBI rule requiring customers to be notified 24 hours before a recurring debit; customers can pause the mandate in response |
| Tier-1 | The deterministic lookup-table rule engine that resolves ~65-75% of cases without LLM involvement |
| Tier-2 | The Claude reasoning agent that handles ambiguous/composite cases (~25-35% of the batch) |
| Compliance Gate | The unconditional, non-LLM code gate that enforces NPCI/RBI rules on every proposed action before execution |
| Action Allow-List | The fixed set of actions that Tier-2 (Claude) can propose; no action outside this list is executable |
| Held-Out Set | The 20% of synthetic mandate events reserved before rule-writing begins; used for honest final evaluation |
| Hinglish | Hindi-English code-mixed language used in customer communications in India |
| Recovery Rate | Percentage of failed mandates where the recovery action resulted in a successful payment |
| False Escalation Rate | Percentage of cases sent to human review unnecessarily (i.e., where automated recovery would have succeeded) |
| Dunning | The process of contacting customers about failed payments; dunning tools automate this for subscription businesses |
| NPCI | National Payments Corporation of India -- governs UPI, e-NACH, and related payment rails |
| TPAP | Third-Party Application Provider -- apps like PhonePe, Google Pay that surface NPCI notifications |
| Bounce Fee | The fee charged when a recurring debit fails due to insufficient funds; Rs. 200-500 for e-NACH, Rs. 0 for UPI Autopay |

---

## Appendix A — 13-Day Build Plan

| Days | Date | Focus |
|---|---|---|
| 1-2 | Aug 23-24 | Finalize taxonomy; generate synthetic dataset with ground-truth labels; split held-out set |
| 3-5 | Aug 25-27 | Build Tier-1 deterministic rule engine end-to-end on the full batch; unit test all six categories |
| 6-8 | Aug 28-30 | Integrate Claude for Tier-2 with strict structured-output constraints; build the compliance gate as an independently-testable module; wire in Razorpay test-mode APIs |
| 9-10 | Aug 31-Sep 1 | Build the append-only audit log and dashboard |
| 11 | Sep 2 | Run the full held-out evaluation; compute honest metrics; fix anything embarrassing |
| 12 | Sep 3 | Polish demo exactly per Section 28; record the 5-minute pitch video; write README + architecture diagram |
| 13 | Sep 4-5 | Buffer for re-recording, repo cleanup, submission. Do not start anything new this late. |

## Appendix B — Submission Checklist

- [ ] Public GitHub repo with a clean README and setup instructions
- [ ] Architecture diagram (reuse Section 12)
- [ ] 5-minute pitch video following Section 28 — The compliance override moment must be unmissable
- [ ] BUILD_LOG.md with genuine real failures encountered (e.g., Claude proposing out-of-allow-list action before schema was tightened)
- [ ] Held-out evaluation metrics reported honestly, including anything unflattering
- [ ] Zero compliance violations in the final executed batch — verify before recording the demo (run evaluator, assert compliance_violations_executed == 0)
- [ ] Unit tests for every compliance gate rule committed to the repo

---

*Master Project Document for Aegis -- v1.0 -- Generated from PRD_Aegis.md -- 2026-08-23*
