# API Reference — Aegis

> **Status:** Canonical reference | Update whenever an endpoint signature changes.

---

## Internal REST API

All endpoints are prefixed with `/api/v1/`. The frontend API client (`dashboard/src/api/aegis.ts`) consumes these endpoints exclusively.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/recovery/batch` | Upload CSV of failed mandates; returns `batch_id` immediately |
| GET | `/api/v1/recovery/batch/{batch_id}` | Poll batch processing results |
| GET | `/api/v1/mandates/{id}` | Full decision trail for a single mandate |
| GET | `/api/v1/metrics` | Summary metrics (recovery rate, tier split, violations) |
| GET | `/api/v1/audit` | Paginated audit log |
| GET | `/api/v1/human-review` | Human review queue |
| POST | `/webhooks/razorpay` | Receive Razorpay subscription webhook events |

---

### `POST /api/v1/recovery/batch`

**Description:** Accept a multipart CSV upload of failed mandate events. Validate, process through the two-tier pipeline, and return the batch ID for polling.

**Request:**
```
Content-Type: multipart/form-data
Body: file (CSV, headers matching MandateEvent schema)
```

**Response `202 Accepted`:**
```json
{
  "batch_id": "uuid-string",
  "status": "complete",
  "record_count": 52,
  "parse_errors": [],
  "metrics": {
    "total_records": 52,
    "tier1_count": 37,
    "tier2_count": 15,
    "tier1_pct": 71.2,
    "recovery_rate": 0.654,
    "rs_recovered": 234500,
    "rs_at_risk": 512000,
    "compliance_violations_caught": 3,
    "compliance_violations_executed": 0
  }
}
```

> **Phase 9 note:** After Phase 9 is implemented, the `POST /api/v1/recovery/batch` endpoint still returns synchronously for CSV uploads. The `/webhooks/razorpay` endpoint changes to `{ status: "queued", job_id }` (async) — see the webhook section below.

**CSV Headers:**
```
mandate_id, customer_id, amount, mandate_type, product_category,
decline_code, days_since_salary_credit, prior_bounce_count,
is_revocable, attempt_number, timestamp
```

---

### `GET /api/v1/recovery/batch/{batch_id}`

**Description:** Poll the processing result for a batch. Returns full per-mandate decision data once status is `"complete"`.

**Response `200 OK`:**
```json
{
  "batch_id": "uuid-string",
  "status": "complete",
  "metrics": {
    "total_records": 52,
    "tier1_count": 37,
    "tier2_count": 15,
    "tier1_pct": 71.2,
    "recovery_rate": 0.654,
    "rs_recovered": 234500,
    "rs_at_risk": 512000,
    "compliance_violations_caught": 3,
    "compliance_violations_executed": 0
  },
  "decisions": [
    {
      "mandate_id": "uuid",
      "tier_that_decided": 1,
      "decline_code": "INSUFFICIENT_FUNDS",
      "proposed_action": "SCHEDULE_POST_SALARY",
      "compliance_approved": true,
      "final_action": "SCHEDULE_POST_SALARY",
      "outcome": "executed",
      "rationale": "debit_before_salary_credit",
      "confidence": null,
      "hinglish_message": null
    }
  ]
}
```

---

### `GET /api/v1/mandates/{id}`

**Description:** Full decision trail for a single mandate, including compliance gate result and Hinglish message if drafted.

**Response `200 OK`:**
```json
{
  "mandate_id": "uuid",
  "customer_id": "CUST-042",
  "amount": 45000,
  "mandate_type": "ENACH",
  "decline_code": "NON_REVOCABLE_HARD_DECLINE",
  "tier_that_decided": 2,
  "proposed_action": "RETRY_AFTER_BACKOFF",
  "compliance_check_result": {
    "approved": false,
    "violation_blocked": true,
    "violation_rule": "non_revocable_mandate_no_auto_retry"
  },
  "final_action": "ESCALATE_TO_HUMAN",
  "outcome": "escalated",
  "rationale": "Groq (Llama) proposed RETRY_AFTER_BACKOFF; compliance gate rejected",
  "confidence": 0.72,
  "hinglish_message": "Aapka EMI payment ke baare mein hamare team se baat karein.",
  "alternatives_considered": ["SEND_HINGLISH_NUDGE", "NO_ACTION_MONITORING"],
  "audit_entry_hash": "sha256-string"
}
```

---

### `GET /api/v1/metrics`

**Description:** Aggregate metrics for the most recent batch or all-time. Used by the dashboard front page.

**Query params:** `?batch_id=uuid` (optional; omit for all-time)

**Response `200 OK`:**
```json
{
  "rs_recovered": 234500,
  "rs_at_risk": 512000,
  "recovery_pct": 45.8,
  "tier1_pct": 71.2,
  "tier2_pct": 28.8,
  "compliance_violations_caught": 3,
  "compliance_violations_executed": 0,
  "recovery_by_category": {
    "INSUFFICIENT_FUNDS": 0.52,
    "BANK_TECHNICAL_DECLINE": 0.88,
    "MANDATE_PAUSED": 0.40,
    "AFA_REQUIRED": 0.67,
    "MANDATE_EXPIRED": 0.71,
    "NON_REVOCABLE_HARD_DECLINE": 0.0
  },
  "false_escalation_rate": 0.09
}
```

---

### `GET /api/v1/audit`

**Description:** Paginated audit log. Every mandate event produces exactly one entry.

**Query params:** `?page=1&page_size=50&batch_id=uuid`

**Response `200 OK`:**
```json
{
  "total": 1024,
  "page": 1,
  "page_size": 50,
  "entries": [
    {
      "entry_id": 1,
      "mandate_id": "uuid",
      "timestamp": "2026-08-23T10:00:00Z",
      "tier_that_decided": 1,
      "proposed_action": "SCHEDULE_POST_SALARY",
      "compliance_check_result": { "approved": true, "violation_blocked": false },
      "final_action": "SCHEDULE_POST_SALARY",
      "outcome": "executed"
    }
  ]
}
```

---

### `GET /api/v1/human-review`

**Description:** Returns all mandates in the human review queue, ordered by creation time (oldest first).

**Response `200 OK`:**
```json
{
  "total": 4,
  "items": [
    {
      "review_id": "uuid",
      "mandate_id": "uuid",
      "reason": "non_revocable_mandate_hard_decline",
      "compliance_rule": "non_revocable_mandate_no_auto_retry",
      "created_at": "2026-08-23T10:05:00Z",
      "resolved_at": null,
      "resolved_by": null
    }
  ]
}
```

---

### `POST /webhooks/razorpay`

**Description:** Receives Razorpay subscription lifecycle webhook events. Validates HMAC signature.

**Phase 1–8 (single-tenant):** Validates HMAC using `RAZORPAY_WEBHOOK_SECRET` env var and processes inline.

**Phase 9 (multi-tenant):** Validates HMAC against per-tenant encrypted secret (iterates active tenants). On match, enqueues an ARQ job and returns `200 OK` in < 1 second. Does not process inline. Response shape: `{ status: "queued", job_id: "...", event: "payment.failed" }`.

**Razorpay Webhook Events:**

| Event | Action |
|---|---|
| `subscription.pending` | Fires when charge fails and subscription moves active→pending |
| `subscription.charged` | Fires on successful charge/retry |
| `payment.failed` | Update mandate event status; trigger recovery pipeline |
| `subscription.activated` | Confirm recovery success |

---

## Razorpay Subscriptions API

All calls use test-mode API keys exclusively. Never use live keys.

### Resume Subscription (for `RETRY_AFTER_BACKOFF`)

```
POST https://api.razorpay.com/v1/subscriptions/{id}/resume
Authorization: Basic base64(RAZORPAY_KEY_ID:RAZORPAY_KEY_SECRET)
```

```python
async def resume_subscription(subscription_id: str) -> dict:
    return await razorpay_client.subscriptions.resume({
        "subscription_id": subscription_id,
        "resume_at": "now"
    })
```

### Pause Subscription (for `SCHEDULE_POST_SALARY`)

```
POST https://api.razorpay.com/v1/subscriptions/{id}/pause
```

```python
async def schedule_post_salary(subscription_id: str, resume_at: int) -> dict:
    await razorpay_client.subscriptions.pause({
        "subscription_id": subscription_id,
        "pause_at": "now"
    })
    # Resume is scheduled separately at salary-credit date
```

---

## Razorpay Payment Links API

### Create Payment Link (for `SEND_UPI_INTENT_PUSH` and `SEND_MANDATE_RENEWAL_LINK`)

```
POST https://api.razorpay.com/v1/payment_links
```

```python
async def create_recovery_payment_link(event: MandateEvent, message: str) -> dict:
    return await razorpay_client.payment_links.create({
        "amount": event.amount * 100,  # Paise
        "currency": "INR",
        "description": f"Payment recovery — {event.mandate_id}",
        "upi_link": True,              # UPI-intent link for AFA-required cases
        "notify": {"sms": False, "email": False},
        "notes": {
            "mandate_id": event.mandate_id,
            "recovery_action": "UPI_INTENT_PUSH"
        }
    })
```

---

## Mock Notification Stub

The mock stub logs notification intent without actually sending. Judges care about decision logic, not a WhatsApp API key.

```python
class MockNotificationService:
    """
    Simulates WhatsApp/SMS notification for the hackathon demo.
    All output goes to notification_log.jsonl and structured logger.
    """
    def __init__(self, log_file: str = "notification_log.jsonl"):
        self.log_file = log_file

    def send(self, customer_id: str, message: str, channel: str) -> dict:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "customer_id": customer_id,
            "channel": channel,     # "whatsapp" | "sms"
            "message": message,
            "status": "MOCKED -- would send in production"
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"[MOCK] would send via {channel} to {customer_id}: {message[:50]}...")
        return entry
```

---

## Test-Mode Razorpay Setup

**Create a test Plan and Subscription (one-time setup):**

```
POST https://api.razorpay.com/v1/plans
{
  "period": "monthly",
  "interval": 1,
  "item": { "name": "Aegis Test Plan", "amount": 100000, "currency": "INR" }
}
```

```
POST https://api.razorpay.com/v1/subscriptions
{
  "plan_id": "plan_XXX",
  "total_count": 12,
  "customer_notify": 0,
  "notes": { "customer_id": "CUST-001" }
}
```

**Demo trick:** Use Razorpay's dashboard "Test Subscriptions charge simulator" to manually trigger subscription charge as success or failure on demand. Do not wait for real billing-cycle timers during the demo.

---

*Source: Master_Aegis.md §10, §15 | Last updated: 2026-08-23*
