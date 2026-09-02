# Future Plans — Aegis

> **Status:** Reference only. Read after the MVP is fully working.
> Do not implement anything in this document until Day 11+ with confirmed spare time.
> The stretch goal (predictive at-risk scorer) is the only item worth considering before the deadline.

---

## Stretch Goal — Predictive At-Risk Scorer

**Condition:** Only attempt this if the MVP dashboard is fully working by end of Day 10 and you have 3+ spare days.

**What it does:** Predicts the probability of mandate failure before it occurs, based on account and salary-cycle features. This converts Aegis from a reactive dunning tool ("why did it fail?") to a predictive one ("who will fail next week?").

**Why it matters for the demo:** It is the single best answer to "what would you build next?" and the strongest differentiator from a basic rule engine. Mention it in the demo close beat even if not implemented.

**Implementation:**

```python
from sklearn.linear_model import LogisticRegression
import numpy as np

def extract_atrisk_features(event: MandateEvent) -> np.ndarray:
    """
    Feature engineering for at-risk prediction.
    All features are available before a mandate attempt occurs.
    """
    afa_threshold = 15000  # General; use product_category for SIP/insurance
    return np.array([
        event.days_since_salary_credit / 30.0,          # Normalised salary cycle position
        event.prior_bounce_count / 5.0,                 # Normalised bounce history
        event.amount / afa_threshold,                   # Amount relative to AFA threshold
        event.attempt_number / 3.0,                     # Normalised attempt count
        1.0 if event.mandate_type == "ENACH" else 0.0, # ENACH flag (higher bounce cost)
        0.0 if event.is_revocable else 1.0,            # Non-revocable flag
    ])

def build_atrisk_classifier(training_events: list[MandateEvent]) -> LogisticRegression:
    """
    Trains a logistic regression classifier on historical mandate events.
    Label: 1 if the mandate failed (any non-SUCCESS outcome), 0 if it succeeded.
    """
    X = np.array([extract_atrisk_features(e) for e in training_events])
    y = np.array([1 if e.decline_code != "SUCCESS" else 0 for e in training_events])
    model = LogisticRegression(max_iter=200)
    model.fit(X, y)
    return model

def score_atrisk(model: LogisticRegression, event: MandateEvent) -> float:
    """Returns probability of failure: 0.0 (safe) to 1.0 (high risk)."""
    features = extract_atrisk_features(event).reshape(1, -1)
    return model.predict_proba(features)[0][1]
```

**Dashboard addition:** Add an `at_risk_score` column to the MandateList component. Flag any score above 0.7 in amber.

**Honest caveat:** On synthetic data, this model will not produce meaningful real-world accuracy. The value is architectural — demonstrating the intent to move from reactive to predictive. If asked about model accuracy during the panel, be honest: "On synthetic data, the model learns the generator's distribution, not real customer behaviour. The value here is the feature engineering and the integration pattern."

---

## Phase 2 — Predictive At-Risk Scoring (Post-Hackathon)

**What:** Logistic regression (or gradient boosted tree) on real mandate history to flag at-risk mandates before the debit attempt.

**Why it matters:** Converts Aegis from reactive ("why did it fail?") to predictive ("who will fail next week?"). Allows proactive customer communication before bounce fees accrue.

**Data requirements:** Minimum 4–6 weeks of real mandate data with labelled outcomes. Cannot be built meaningfully on synthetic data.

**Features to engineer:**
- Salary credit date vs. debit date delta (from bank account metadata)
- Prior bounce rate (rolling 90-day window)
- Amount / AFA threshold ratio
- Mandate age and historical compliance rate
- Day-of-month seasonality (salary cycle patterns)

---

## Phase 3 — Expanded Failure Categories

**What:** Expand the six-category taxonomy to 15+ decline codes based on real NPCI/bank return code data.

**Priority additions:**
- Bank-specific codes: HDFC (`INSUFFICIENT_BALANCE_HDFC`), SBI (`SBI_TECHNICAL`), Kotak (`KOTAK_LIMIT_EXCEEDED`)
- NACH-specific: `NACH_ACCOUNT_CLOSED`, `NACH_INVALID_IFSC`, `NACH_SIGNATURE_MISMATCH`
- UPI Autopay-specific: `UPI_HANDLE_INACTIVE`, `UPI_COLLECT_EXPIRED`

**Why deferred:** Six well-modeled categories beat twenty shallow ones. The taxonomy is the intellectual core; expand only with real decline code data to model correctly.

---

## Phase 4 — Real Notification Integration

**What:** Replace the mock notification stub with actual delivery channels.

**Priority order:**
1. WhatsApp Business API (Hinglish nudge delivery — highest open rate in India)
2. SMS via Twilio or MSG91 (fallback for non-WhatsApp users)
3. IVR / voice call integration for high-value EMI recovery (Rs. 50,000+)

**A/B testing:** Once multiple message variants exist, run A/B tests on Hinglish message framing (loss-aversion vs. gain-framing vs. urgency) to optimise recovery rate per category.

**Compliance note:** All real notification delivery must comply with TRAI DND regulations and WhatsApp Business Policy. Customer opt-in must be captured at mandate registration time.

---

## Phase 5 — Bandit-Based Retry Optimisation

**What:** A contextual bandit model that learns optimal retry timing based on customer-level salary cycle, historical bounce patterns, and day-of-week/time-of-day signals.

**Why deferred:** A bandit model requires weeks of real interaction data to converge. On synthetic data, it learns the generator's distribution — not useful. Do not build this until Aegis is in production with real mandate data.

**Features for the bandit context vector:**
- Day of month relative to estimated salary credit date
- Time of day (salary accounts often receive credits at specific times)
- Prior bounce count in the current cycle
- Customer tier / account age
- Mandate type (UPI Autopay vs. e-NACH)

---

## Phase 6 — Razorpay Product Integration

**What:** Aegis becomes a module within Razorpay's Subscription Recovery Agent product.

> **Note on integration sequencing:** Phase 9 of the current build implements the **sidecar integration model** — Aegis is a standalone multi-tenant service that NBFCs connect to via a single webhook URL. This is the recommended first production deployment. The Razorpay product embedding described here is a later-stage partnership scenario (post-commercial traction), not the initial go-to-market architecture. See `project-context/architecture.md` Production Architecture section for the sidecar model detail.

**Integration points (partnership scenario):**
- Dashboard embedded in Razorpay's merchant portal (not a standalone app)
- Compliance config editable from the Razorpay merchant dashboard
- Mandate event ingestion via native Razorpay webhook subscription (no CSV upload)
- Hinglish message delivery via Razorpay's existing WhatsApp integration
- Audit log exposed via Razorpay's existing reporting APIs

---

## Resolved Questions and Architectural Decisions

All open questions from Master_Aegis.md §32 are fully resolved:

**Q1 — Held-out set size:**
- **Status: Resolved (Phase 1).**
- **Decision:** Generate 500 records; deterministically hold out 100 records (20%, seed 42) into `data/synthetic_held_out.csv`. This yields statistically significant evaluation counts across all six decline categories.
- **Implemented in:** `synthetic/generator.py` (splitting logic) and `plans/phase-1-foundation.md`.

**Q2 — AFA threshold for e-NACH SIPs:**
- **Status: Resolved (Phase 1 & 3).**
- **Decision:** `product_category` field (`subscription`, `loan_emi`, `sip`, `insurance`) is added to `MandateEvent`. The compliance gate's `_get_afa_threshold()` dynamically inspects `product_category` and looks up `AFA_THRESHOLD_SIP_INSURANCE` (Rs. 1,00,000) or `AFA_THRESHOLD_GENERAL` (Rs. 15,000) from `compliance_config.yaml`.
- **Implemented in:** `models/mandate_event.py`, `core/compliance_gate.py`, and `config/loader.py`.

**Q3 — Hinglish message visibility:**
- **Status: Resolved (Phase 5 & 7).**
- **Decision:** The dashboard displays the drafted Hinglish message preview in `MandateDetailDrawer` for any event where Tier-2 generated one, regardless of whether the final executed action was modified by the compliance gate.
- **Implemented in:** `core/orchestrator.py` (preserving `hinglish_message` on `RecoveryDecision`), `models/recovery_decision.py`, and `dashboard/src/components/HinglishMessagePreview.tsx`.

**Q4 — Human review queue resolution:**
- **Status: Resolved (Phase 6 & 7).**
- **Decision:** Dedicated `POST /api/v1/human-review/{review_id}/resolve` endpoint updates the `resolved_at` timestamp in `human_review_queue`. `HumanReviewQueue.tsx` surfaces a "Mark as Resolved" action button that optimistic-removes the row upon success.
- **Implemented in:** `models/db.py` (`HumanReviewQueueORM`), `api/routes/human_review.py`, and `dashboard/src/components/HumanReviewQueue.tsx`.

**Q5 — Batch upload and intake format:**
- **Status: Resolved (Phase 6 & 9).**
- **Decision:** Multipart CSV upload via `POST /api/v1/recovery/batch` serves as the primary demo/batch interface. Single-event webhook ingestion via `POST /webhooks/razorpay` (with async Redis/ARQ workers in Phase 9) handles real-time asynchronous mandate processing.
- **Implemented in:** `api/routes/recovery.py`, `api/routes/webhooks.py`, and `workers/mandate_worker.py`.

---

*Source: Master_Aegis.md §14 (stretch goal), §30, §32 | Last updated: 2026-08-23*
