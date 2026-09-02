# Aegis — Project Context

> **Revision:** 1.0 | **Track:** 03 — AI Revenue Recovery | **Composite Win Probability:** 8.5/10

---

## What is Aegis?

Aegis is a compliant, two-tier failure diagnosis and recovery agent for UPI Autopay and e-NACH mandates used by Indian subscription businesses and NBFCs. It answers one of the most painful, unsolved problems in Indian fintech: *"Why did my customer's recurring payment fail, and what is the legally compliant action I should take next?"*

The core insight is that every global dunning tool — Stripe Smart Retries, Churnkey, Churn Buster, Butter Payments — is built for card rails. None of them model NPCI mandate mechanics, RBI compliance rules, or the structural difference between UPI Autopay (zero consumer bounce fee) and NACH (Rs. 200–500 consumer penalty per bounce). Aegis is built exclusively for this context.

**In one sentence:** Ingest a batch of failed/at-risk mandate events, a deterministic Tier-1 rule engine resolves ~65–75% of cases instantly, ambiguous cases go to a Groq (Llama) Tier-2 reasoning step constrained to a fixed action allow-list, all proposed actions pass through a non-LLM compliance gate that cannot be bypassed, actions execute against Razorpay test-mode APIs, every decision is appended to an immutable audit log, and a dashboard reports recovery rate, rupees recovered vs. at risk, and compliance violations caught.

---

## The Problem

### Revenue Leak

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

Every global dunning tool is card-rail native. None of them model:
- NPCI mandate mechanics
- Non-revocable loan mandate constraints
- The salary-cycle-aware retry window
- UPI Autopay vs. NACH structural differences
- The AFA threshold routing rule
- The 24h pre-debit notice mandatory pause

### Business Signal

- Explicitly named on the Buildathon page as an example direction ("Mandate retry sequencer," "Hinglish voice recovery")
- Razorpay's engineering blog reportedly published a playbook on this problem before the hackathon
- The market: every NBFC, subscription SaaS, OTT platform, insurance company, and fitness app on UPI Autopay or e-NACH in India is affected

---

## Vision and Philosophy

### North Star

Build the first India-native, compliance-aware dunning intelligence layer that treats UPI Autopay and e-NACH as first-class citizens — not bolted-on edge cases of a card-first system.

### Core Philosophical Commitment

> "The rule engine decides. The LLM explains and drafts. Compliance is unconditional."

Three specific implications:

1. **Tier-1 is the workhorse.** If Tier-1 (deterministic rules) is routing more than 30% of cases to Tier-2 (LLM), the rule engine is not doing its job. That is a negative signal, not sophistication.
2. **The compliance gate is unconditional.** No LLM output can bypass it. If the LLM proposes a retry on a non-revocable mandate after two hard declines, the gate blocks it, logs the override, and escalates to human.
3. **Honesty is the strategy.** Report recovery rate on the held-out test set. Report false-escalation rate. Show compliance violations caught vs. those that reached execution (must be zero of the latter).

---

## Design Principles

| # | Principle | Operational Meaning |
|---|---|---|
| P1 | Majority deterministic | Tier-1 resolves ~65–75% of cases; LLM handles only the ambiguous remainder |
| P2 | Compliance is unconditional | The compliance gate cannot be bypassed by any LLM output, configuration, or user action |
| P3 | Six categories, done well | Only the six failure categories in the taxonomy are modeled; depth beats breadth |
| P4 | Salary-cycle-aware | Retry timing is informed by days-since-salary-credit, not a blind D+1/D+3 schedule |
| P5 | Held-out evaluation | Metrics are reported on a test slice not seen while writing rules or prompts |
| P6 | Human escalation is a feature | Non-revocable mandates escalating to human review is the correct outcome, not a failure |
| P7 | Hinglish as a first-class output | Recovery messages drafted by the LLM are in Hinglish by default — India-first, not translated |
| P8 | Transparent AI judgment | Every Tier-2 decision shows: rationale, confidence, alternatives considered, compliance result |

---

## The Six Failure Categories

This taxonomy is the intellectual core of the product. Every rule in Tier-1, every LLM prompt in Tier-2, and every compliance rule in the gate is derived from this table.

| Code | Category | Root Cause | Correct Action |
|---|---|---|---|
| `INSUFFICIENT_FUNDS` | Insufficient balance | Debit attempted before salary credit | Reschedule to post-salary-date window — not a blind D+1 |
| `AFA_REQUIRED` | Above Rs. 15,000 AFA threshold | NPCI blocks silent auto-debit above threshold | Trigger UPI-intent push requiring explicit approval — never silent retry |
| `MANDATE_PAUSED` | Paused after 24h pre-debit alert | RBI-mandated notice triggered a pause | Loss-aversion-framed Hinglish nudge before the mandate lapses |
| `BANK_TECHNICAL_DECLINE` | Bank-side technical failure | Timeout / bank downtime | Safe to retry once, after a backoff window |
| `NON_REVOCABLE_HARD_DECLINE` | Loan EMI, 2nd hard decline | Cannot legally auto-retry a non-revocable mandate | Escalate to human — zero further auto-retries |
| `MANDATE_EXPIRED` | Token/mandate lapsed | e-mandate validity window passed | Send a new mandate registration link, not a retry |

---

## The Action Allow-List

Tier-2 (Groq/Llama) can only propose actions from this fixed list. It cannot invent new actions.

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
```

---

## Two-Tier Architecture Mental Model

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
    Tier 2: Groq (Llama) Reasoning Agent
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

---

## User Personas

### Persona 1 — Finance-Ops User at an NBFC (Primary)

**Name:** Meera, Collections Analyst at a lending NBFC

**Context:** Manages a portfolio of 5,000+ active EMI mandates via Razorpay; currently handles failed mandates by running blind D+1/D+3 retries and manual collections calls.

**Pain Points:**
- No visibility into why a mandate failed (just a raw decline code)
- Fixed retry schedule causes unnecessary NACH bounce fees when funds are genuinely not available
- Non-revocable loan mandates occasionally get blindly retried, creating legal exposure
- No automated Hinglish customer communication for paused mandates

**Goal:** Load a batch of failed mandates, see what is recoverable and what requires human action, and send appropriate customer nudges — in one workflow.

**How Aegis helps:** Meera loads a CSV, clicks Run Recovery, sees 70%+ resolved in under a second with reasons, sees 3 ambiguous cases routed to the LLM with Hinglish messages drafted, sees the non-revocable EMI case escalated to human with the compliance rule cited.

---

### Persona 2 — Subscription SaaS Finance Team (Primary)

**Name:** Rajesh, CFO of a B2B SaaS company on UPI Autopay

**Context:** 400 subscribers, ~14% monthly payment failure rate; manually reviews each failure.

**Pain Point:** Cannot distinguish "retry tomorrow" (BANK_TECHNICAL_DECLINE) from "send a new mandate registration link" (MANDATE_EXPIRED) — they look the same in the raw webhook event.

**Goal:** Automate the triage of failed mandates so the finance team only sees cases that genuinely need human judgment.

---

### Persona 3 — Razorpay Revenue Recovery Team (Secondary)

**Name:** Ananya, PM on Razorpay's Subscription Recovery Agent product

**Context:** Building agent-native recovery features for the Subscriptions product; needs a reference architecture for compliant automated dunning.

**Goal:** Understand how a two-tier compliant recovery agent should be architected.

---

### Persona 4 — Hackathon Judge (Evaluator)

**What they want to see:** A non-revocable mandate correctly refused and escalated to human; a live Tier-1 vs. Tier-2 split; a compliance-violations-caught count greater than zero but zero that reached execution; honest held-out metrics.

---

## Product Goals and Anti-Goals

### Goals

| ID | Goal |
|---|---|
| G1 | Given a batch of 50+ synthetic failed/at-risk mandate events, correctly classify root cause using a deterministic rule engine for ~65–75% of cases |
| G2 | For ambiguous/composite cases, use Groq (Llama) — constrained to a fixed action allow-list and structured JSON output — to propose a compliant recovery action plus a Hinglish customer message |
| G3 | Enforce hard compliance rules (AFA thresholds, 24h pre-debit notice, non-revocable mandate escalation-only, max retry attempts) via a deterministic compliance gate that the LLM cannot override |
| G4 | Execute chosen actions against Razorpay's test-mode Subscriptions / Payment Links API and log every decision to an append-only audit trail |
| G5 | Report honest held-out metrics: recovery rate by failure category, rupees recovered vs. at risk, zero compliance violations reaching execution, false-escalation rate |
| G6 | Demonstrate at least one deliberate "graceful failure" moment live — a non-revocable EMI mandate correctly refusing a third retry and escalating to human |

### Anti-Goals (Hard Cuts)

| Anti-Goal | Reason |
|---|---|
| Production-grade bandit/survival-analysis/RL optimizer as core deliverable | No real convergence to show on synthetic data |
| Real WhatsApp/voice/telephony integration | A mocked notification stub is sufficient and expected |
| Real customer PII or bank data | 100% synthetic, generated with realistic distributions |
| Covering every NPCI/bank decline code | Six well-modeled categories beat twenty shallow ones |
| Routing more than ~30% of cases to Tier-2 | If more than 30% hit Tier-2, the rule engine is not doing its job |

---

## Glossary

| Term | Definition |
|---|---|
| Aegis | This system — the two-tier failure diagnosis and recovery agent for UPI Autopay and e-NACH mandates |
| UPI Autopay | NPCI's recurring payment mechanism via UPI; zero consumer bounce fee |
| e-NACH | Electronic National Automated Clearing House; traditional recurring debit with Rs. 200-500 consumer bounce fee |
| AFA | Additional Factor of Authentication — NPCI rule requiring explicit customer approval for auto-debits above Rs. 15,000 |
| Non-Revocable Mandate | A mandate (typically loan EMI) that cannot be legally auto-retried after a hard decline |
| 24h Pre-Debit Notice | RBI rule requiring customers to be notified 24 hours before a recurring debit; customers can pause the mandate in response |
| Tier-1 | The deterministic lookup-table rule engine that resolves ~65-75% of cases without LLM involvement |
| Tier-2 | The Groq (Llama) reasoning agent that handles ambiguous/composite cases (~25-35% of the batch) |
| Compliance Gate | The unconditional, non-LLM code gate that enforces NPCI/RBI rules on every proposed action before execution |
| Action Allow-List | The fixed set of actions that Tier-2 can propose; no action outside this list is executable |
| Held-Out Set | The 20% of synthetic mandate events reserved before rule-writing begins; used for honest final evaluation |
| Hinglish | Hindi-English code-mixed language used in customer communications in India |
| Recovery Rate | Percentage of failed mandates where the recovery action resulted in a successful payment |
| False Escalation Rate | Percentage of cases sent to human review unnecessarily |
| Dunning | The process of contacting customers about failed payments |
| NPCI | National Payments Corporation of India — governs UPI, e-NACH, and related payment rails |
| TPAP | Third-Party Application Provider — apps like PhonePe, Google Pay that surface NPCI notifications |
| Bounce Fee | The fee charged when a recurring debit fails due to insufficient funds; Rs. 200-500 for e-NACH, Rs. 0 for UPI Autopay |

---

*Source: Master_Aegis.md §1-7, §33 | Last updated: 2026-08-23*
