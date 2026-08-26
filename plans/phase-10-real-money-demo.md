# Phase 10: Real-Money End-to-End Demo (Live Recovery Proof)

> **Status:** [ ] Not started
> **Estimated duration:** 1–2 days (post-Phase 9, pre-demo-recording)
> **Depends on:** Phase 9 complete (multi-tenancy, auth, ARQ workers, callbacks, observability)
> **Purpose:** Prove the pipeline moves real money — not just reasoning. Close the loop: mandate fails → Aegis decides → action executes → customer pays → webhook confirms → dashboard updates.

---

## Objective

Transform the current "decision-layer-only" demo into a **visually provable, money-moving demo**. Today, the pipeline reasons correctly but every Razorpay call fails silently (synthetic mandate IDs, test-mode UPI restrictions, rate limits). This phase wires the pipeline to **real Razorpay test-mode subscriptions with real customer contact points** so that at least one full recovery cycle can be demonstrated live:

```
Real subscription exists in Razorpay
        → payment.failed webhook fires
        → Aegis classifies + gates
        → Action executes against the REAL subscription
        → Customer receives a real UPI intent push / payment link
        → Customer (the presenter, on their phone) approves the payment
        → Razorpay fires payment.captured webhook
        → Aegis dashboard updates: Rs. recovered increments
        → Audit log records the full trail
```

One completed recovery is enough to prove the thesis. Everything else stays as-is.

---

## Scope

| Sub-phase | Feature | New / modified files |
|---|---|---|
| 10.1 | Razorpay test Plan + Subscription seeding | `scripts/seed_razorpay.py` |
| 10.2 | Live mandate CSV generator (real subscription IDs) | `scripts/make_live_demo_batch.py` |
| 10.3 | Webhook registration + local tunnel for dev / EC2 endpoint for prod | `scripts/register_webhook.py`, nginx config |
| 10.4 | Payment captured webhook handler | `api/routes/webhooks.py` (update) |
| 10.5 | Dashboard: live recovery ticker | `dashboard/src/pages/app/Dashboard.tsx` (update) |
| 10.6 | Demo rehearsal script | `scripts/rehearse_live_demo.sh` |
| 10.7 | End-to-end proof test | `tests/integration/test_live_recovery.py` |

---

## Design Decisions and Rationale

**D1 — Razorpay Test Mode, not Live Mode.**
Live mode requires KYC-verified business entity + bank account. Test mode supports the full subscription lifecycle (create plan → create subscription → simulate charge/failure → payment links → webhooks) without KYC. The demo proves the *pipeline*, not the payment gateway itself. Test-mode money is fake but the API calls, webhooks, and state transitions are identical to live.

**D2 — Seed real subscriptions, don't fabricate mandate IDs.**
The current demo batch uses synthetic `MAND-XXX` IDs that Razorpay has never seen. This phase creates **real Razorpay subscriptions** (via the Plans + Subscriptions API in test mode) and uses their real IDs (`sub_XXXXXX`) in the demo CSV. When Aegis calls `subscription.resume()` on these, Razorpay actually processes the state change.

**D3 — Use the Razorpay Test "Charge Simulator" for failure simulation.**
Razorpay test mode provides a way to simulate `payment.failed` on a subscription by advancing its cycle to a state where the next debit will fail. The seeding script creates subscriptions in a state where the first debit fails, which triggers a real `payment.failed` webhook to our endpoint.

**D4 — UPI Intent Push uses the presenter's real UPI ID.**
The `SEND_UPI_INTENT_PUSH` action creates a Payment Link with `upi_link=true`. In test mode, this link opens a Razorpay test checkout page. The presenter opens this link on their phone, selects any test UPI app (or uses the test VPA), and completes the payment. Razorpay fires `payment.captured` webhook → Aegis dashboard updates. This is the "money movement" moment.

**D5 — Webhook endpoint must be publicly reachable.**
Razorpay sends webhooks to a public HTTPS URL. The EC2 instance at `https://aegis-platform.duckdns.org/webhooks/razorpay` is already publicly reachable with valid SSL. For local development, `ngrok` or `localtunnel` provides a temporary public tunnel.

**D6 — Payment captured handler updates the mandate outcome.**
When `payment.captured` arrives, Aegis:
1. Verifies the HMAC signature
2. Looks up the original `RecoveryDecision` by `notes.mandate_id` (set when the Payment Link was created)
3. Updates the outcome from `executed` to `recovered`
4. Increments the dashboard's `Rs. recovered` metric
5. Writes an audit entry recording the successful recovery

---

## Sequential Implementation Tasks

---

### Sub-phase 10.1 — Razorpay Seeding

#### Task 10.1.1 — Create `scripts/seed_razorpay.py`

```python
# scripts/seed_razorpay.py
"""
Seed Razorpay test mode with real Plans + Subscriptions for the live demo.

Usage:
    python scripts/seed_razorpay.py --count 5

Creates:
    1. A Plan (monthly recurring, e.g. Rs. 500/month)
    2. N Subscriptions on that plan (in various states)
    3. Prints the subscription IDs for use in the demo batch CSV

Requires RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env (test mode keys).
"""
```

The script:
1. Creates a Plan via `client.plan.create()` (monthly, Rs. 500, test mode)
2. Creates N Subscriptions via `client.subscription.create()` with `customer_notify=1`
3. For each subscription, uses the Razorpay test charge simulator to trigger a `payment.failed` on the first debit attempt
4. Prints a table of `{subscription_id, status, next_charge_date}` for the CSV generator

#### Task 10.1.2 — Verify webhook receipt

After seeding, confirm Razorpay sends `payment.failed` webhooks to `https://aegis-platform.duckdns.org/webhooks/razorpay`:
1. Register the webhook in Razorpay Dashboard → Settings → Webhooks (or via API)
2. Check the Aegis audit log for the incoming event
3. Verify the ARQ worker processes it (Phase 9) and writes a `RecoveryDecision`

---

### Sub-phase 10.2 — Live Demo Batch

#### Task 10.2.1 — Create `scripts/make_live_demo_batch.py`

```python
# scripts/make_live_demo_batch.py
"""
Generate a demo CSV using REAL Razorpay subscription IDs (from seed_razorpay.py output).

Usage:
    python scripts/make_live_demo_batch.py --subscriptions sub_XXX sub_YYY sub_ZZZ
"""
```

The script:
1. Takes real subscription IDs as arguments
2. Builds CSV rows with `mandate_id = sub_XXX` (the real Razorpay subscription ID)
3. Sets `decline_code = BANK_TECHNICAL_DECLINE` (safe to retry) for most
4. Sets one row as `AFA_REQUIRED` with `amount > 15000` (triggers UPI intent push)
5. Sets one row as `NON_REVOCABLE_HARD_DECLINE` (triggers escalation — the demo moment)
6. Outputs `data/live_demo_batch.csv`

---

### Sub-phase 10.3 — Webhook Registration + Payment Captured Handler

#### Task 10.3.1 — Create `scripts/register_webhook.py`

```python
# scripts/register_webhook.py
"""
Register the Aegis webhook URL in Razorpay (test mode).

Usage:
    python scripts/register_webhook.py --url https://aegis-platform.duckdns.org/webhooks/razorpay
"""
```

Registers `payment.failed`, `payment.captured`, `subscription.charged`, `subscription.pending` events via the Razorpay Webhooks API.

#### Task 10.3.2 — Update `api/routes/webhooks.py` — Payment Captured Handler

Add a `payment.captured` handler that:
1. Extracts `mandate_id` from the webhook payload's `notes` field
2. Queries `RecoveryDecisionORM` for the matching mandate
3. Updates `outcome` from `"executed"` to `"recovered"`
4. Increments a `rs_recovered` counter (or recomputes from DB)
5. Writes an audit entry: `{"event": "payment_captured", "amount": ..., "mandate_id": ...}`

```python
# In api/routes/webhooks.py (add to the existing handler)

if event_type == "payment.captured":
    mandate_id = payload.get("payload", {}).get("payment", {}).get("notes", {}).get("mandate_id")
    amount = payload.get("payload", {}).get("payment", {}).get("amount", 0) // 100  # paise to rupees
    # Update decision outcome + write audit entry
```

---

### Sub-phase 10.4 — Dashboard Live Recovery Ticker

#### Task 10.4.1 — Update `dashboard/src/pages/app/Dashboard.tsx`

Add a prominent "Rs. Recovered" stat that:
1. Reads from `GET /api/v1/metrics` (which now includes `rs_recovered` from captured payments)
2. Auto-refreshes every 10 seconds (or on WebSocket push in future)
3. Animates on change (count-up effect)

This is the number that goes from ₹0 to ₹500 live on screen during the demo.

---

### Sub-phase 10.5 — End-to-End Proof Test

#### Task 10.5.1 — Create `tests/integration/test_live_recovery.py`

```python
# tests/integration/test_live_recovery.py
"""
Full live recovery cycle test (requires Razorpay test-mode credentials + webhook).

Skipped in CI (no real Razorpay access). Run manually:
    pytest tests/integration/test_live_recovery.py -v --run-live
"""
```

Test flow:
1. Seed one Razorpay subscription
2. Trigger a payment.failed webhook
3. Wait for Aegis to process it (poll audit log)
4. Verify a Payment Link was created (for AFA cases) or subscription was resumed (for BTD cases)
5. Simulate payment.captured webhook
6. Verify dashboard metrics show Rs. recovered > 0

---

### Sub-phase 10.6 — Demo Rehearsal Script

#### Task 10.6.1 — Create `scripts/rehearse_live_demo.sh`

```bash
#!/bin/bash
# Step-by-step rehearsal script for the live demo
# 1. Seed Razorpay subscriptions
# 2. Generate live demo CSV
# 3. Upload via API (or dashboard)
# 4. Show dashboard with real-time recovery
# 5. Open payment link on phone → approve → watch dashboard update
```

---

## The Live Demo Flow (5-Minute Video Update)

| Time | Beat | What to Show |
|---|---|---|
| 0:00–0:30 | Thesis | Dashboard with Rs. 0 recovered / Rs. X at risk |
| 0:30–1:30 | Tier-1 | Upload live CSV → 70% resolved instantly |
| 1:30–2:30 | Tier-2 | Groq reasons through ambiguous cases |
| 2:30–3:00 | Override | Compliance gate blocks non-revocable retry |
| **3:00–4:30** | **LIVE RECOVERY** | **Open Payment Link on phone → approve → dashboard Rs. counter increments → audit trail updates** |
| 4:30–5:00 | Close | "That Rs. 500 just moved. Aegis decided, executed, and proved it — all compliant." |

---

## Acceptance Criteria

- [ ] `scripts/seed_razorpay.py` creates real test subscriptions and prints their IDs
- [ ] Razorpay sends `payment.failed` webhook to Aegis → processed by ARQ worker
- [ ] Aegis executes an action against a REAL subscription ID (resume/pause/payment link)
- [ ] Payment Link opens on a phone → test payment completes
- [ ] `payment.captured` webhook received → outcome updated to `recovered`
- [ ] Dashboard `Rs. recovered` increments from 0 to a non-zero value live on screen
- [ ] Audit log contains the full trail: webhook → decision → action → payment → recovery
- [ ] `compliance_violations_executed == 0` still holds on the live batch
- [ ] Demo video captures the Rs. counter incrementing in real time

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| Razorpay test mode doesn't support subscription.resume() on all states | Medium | Test with seed script first; fall back to Payment Link only |
| Test-mode UPI checkout doesn't work on all devices | Low | Razorpay test checkout works in any browser; use desktop if phone fails |
| Webhook not received (DNS/SSL issue) | Low | Already verified working (403 on unsigned = endpoint is reachable) |
| Groq rate limit during live demo | Low | Pre-warm the batch before recording; keep Tier-2 count low |
| ARQ worker not running on EC2 | Medium | Phase 9 adds `worker` service to docker-compose; verify before demo |

---

## Deliverables

- `scripts/seed_razorpay.py`
- `scripts/make_live_demo_batch.py`
- `scripts/register_webhook.py`
- `scripts/rehearse_live_demo.sh`
- Updated `api/routes/webhooks.py` (payment.captured handler)
- Updated `dashboard/src/pages/app/Dashboard.tsx` (live recovery ticker)
- `tests/integration/test_live_recovery.py`
- Updated `data/live_demo_batch.csv` (real subscription IDs)
- Demo video with real money movement

---

## Documentation Updates

- Update `project-context/demo.md` with the live recovery beat
- Update `project-context/tasks.md` with Phase 10 checklist
- Update `plans/overview.md` Phase 10 status
- Update `README.md` with live recovery proof
