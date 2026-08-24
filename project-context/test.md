# Testing Strategy — Aegis

> **Status:** Living document | Add new test cases as edge cases are discovered. Never remove a test case.
> Run the full suite before every commit. Run the held-out evaluation on Day 12 before recording the demo.

---

## Test Pyramid

```
       [E2E / Held-Out Evaluation]
       Full batch pipeline on the reserved test set.
       Asserts: compliance_violations_executed == 0
       Run: Day 11, and once more before recording demo.

    [Integration Tests]
    Full batch pipeline with deliberate injections.
    API endpoint responses. Audit log completeness.
    Run: After each major feature is complete.

[Unit Tests]
Each rule in Tier-1. Every compliance gate check.
Tier-2 Pydantic schema validation. Audit write.
Run: Before every commit. CI runs these on every push.
```

---

## Unit Tests — Tier-1 Rule Engine

File: `tests/unit/test_tier1.py`

These tests verify that the rule engine never calls the LLM and resolves all six categories deterministically.

```python
def test_insufficient_funds_scheduled():
    event = MandateEvent(decline_code="INSUFFICIENT_FUNDS", days_since_salary_credit=3, prior_bounce_count=1)
    result = tier1_engine.classify(event)
    assert result.action == "SCHEDULE_POST_SALARY"
    assert not result.is_ambiguous
    assert result.tier == 1

def test_insufficient_funds_high_bounce_escalated():
    """Prior bounce count > 3 triggers escalation regardless of decline code."""
    event = MandateEvent(decline_code="INSUFFICIENT_FUNDS", prior_bounce_count=4)
    result = tier1_engine.classify(event)
    assert result.action == "ESCALATE_TO_HUMAN"
    assert not result.is_ambiguous

def test_afa_required_routes_to_intent_push():
    event = MandateEvent(decline_code="AFA_REQUIRED", amount=16000, mandate_type="UPI_AUTOPAY")
    result = tier1_engine.classify(event)
    assert result.action == "SEND_UPI_INTENT_PUSH"
    assert not result.is_ambiguous

def test_afa_borderline_routes_to_tier2():
    """Amount within 10% of AFA threshold is ambiguous."""
    event = MandateEvent(decline_code="AFA_REQUIRED", amount=14000, mandate_type="UPI_AUTOPAY")
    result = tier1_engine.classify(event)
    assert result.is_ambiguous
    assert result.reason == "borderline_afa_threshold"

def test_mandate_paused_sends_nudge():
    event = MandateEvent(decline_code="MANDATE_PAUSED")
    result = tier1_engine.classify(event)
    assert result.action == "SEND_HINGLISH_NUDGE"
    assert not result.is_ambiguous

def test_bank_technical_retried():
    event = MandateEvent(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=1, mandate_type="UPI_AUTOPAY")
    result = tier1_engine.classify(event)
    assert result.action == "RETRY_AFTER_BACKOFF"
    assert not result.is_ambiguous

def test_bank_technical_max_attempts_escalated():
    """attempt_number >= max for ENACH (2) triggers escalation."""
    event = MandateEvent(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=2, mandate_type="ENACH")
    result = tier1_engine.classify(event)
    assert result.action == "ESCALATE_TO_HUMAN"

def test_non_revocable_escalated():
    event = MandateEvent(decline_code="NON_REVOCABLE_HARD_DECLINE", is_revocable=False)
    result = tier1_engine.classify(event)
    assert result.action == "ESCALATE_TO_HUMAN"
    assert not result.is_ambiguous

def test_mandate_expired_sends_renewal_link():
    event = MandateEvent(decline_code="MANDATE_EXPIRED")
    result = tier1_engine.classify(event)
    assert result.action == "SEND_MANDATE_RENEWAL_LINK"
    assert not result.is_ambiguous

def test_unknown_decline_code_routes_to_tier2():
    """Unknown codes must always route to Tier-2, never be silently handled."""
    event = MandateEvent(decline_code="UNKNOWN_CODE_XYZ")
    result = tier1_engine.classify(event)
    assert result.is_ambiguous
    assert result.reason == "unknown_decline_code"
```

**Non-functional assertion (enforced in test setup):**
```python
# Verify Tier-1 makes zero LLM calls
import unittest.mock as mock

def test_tier1_makes_no_llm_calls():
    with mock.patch("core.tier2_agent.tier2_reason") as mock_llm:
        for code in ALL_DECLINE_CODES:
            event = MandateEvent(decline_code=code)
            tier1_engine.classify(event)
        mock_llm.assert_not_called()
```

---

## Unit Tests — Compliance Gate (Critical)

File: `tests/unit/test_compliance_gate.py`

These are the most important tests in the project. Each rule has:
- A test proving it activates correctly (violation is caught)
- A test proving a compliant action passes through

The ability to say "we have tests proving the compliance gate cannot be bypassed" is a strong answer in the panel round.

```python
# --- Rule 1: Non-Revocable Mandate ---

def test_non_revocable_retry_blocked():
    event = MandateEvent(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.final_action == "ESCALATE_TO_HUMAN"
    assert result.violation_blocked is True
    assert result.violation_rule == "non_revocable_mandate_no_auto_retry"

def test_non_revocable_schedule_blocked():
    event = MandateEvent(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = compliance_gate.check(event, proposed_action="SCHEDULE_POST_SALARY")
    assert not result.approved
    assert result.violation_blocked is True

def test_non_revocable_escalate_passes():
    """ESCALATE_TO_HUMAN is the only valid action for non-revocable hard declines."""
    event = MandateEvent(is_revocable=False, decline_code="NON_REVOCABLE_HARD_DECLINE")
    result = compliance_gate.check(event, proposed_action="ESCALATE_TO_HUMAN")
    assert result.approved
    assert result.violation_blocked is False

# --- Rule 2: Max Retry Attempts ---

def test_max_retries_enach_blocked():
    """ENACH max is 2. attempt_number=2 must block any retry."""
    event = MandateEvent(mandate_type="ENACH", attempt_number=2, decline_code="BANK_TECHNICAL_DECLINE", is_revocable=True, amount=5000)
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.violation_blocked is True

def test_max_retries_upi_within_limit_passes():
    """UPI Autopay max is 3. attempt_number=2 should pass."""
    event = MandateEvent(mandate_type="UPI_AUTOPAY", attempt_number=2, decline_code="BANK_TECHNICAL_DECLINE", is_revocable=True, amount=5000)
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert result.approved

# --- Rule 3: AFA Threshold ---

def test_afa_silent_retry_blocked():
    event = MandateEvent(amount=16000, decline_code="AFA_REQUIRED", mandate_type="UPI_AUTOPAY", is_revocable=True, attempt_number=1)
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.final_action == "SEND_UPI_INTENT_PUSH"
    assert result.violation_rule.startswith("afa_threshold_requires_intent_push")

def test_afa_intent_push_passes():
    """SEND_UPI_INTENT_PUSH is the correct action for AFA-required cases."""
    event = MandateEvent(amount=16000, decline_code="AFA_REQUIRED", mandate_type="UPI_AUTOPAY", is_revocable=True, attempt_number=1)
    result = compliance_gate.check(event, proposed_action="SEND_UPI_INTENT_PUSH")
    assert result.approved

def test_below_afa_threshold_retry_passes():
    event = MandateEvent(amount=10000, decline_code="BANK_TECHNICAL_DECLINE", mandate_type="UPI_AUTOPAY", is_revocable=True, attempt_number=1)
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert result.approved

# --- Rule 4: 24h Pre-Debit Notice ---

def test_paused_mandate_retry_blocked():
    event = MandateEvent(decline_code="MANDATE_PAUSED", is_revocable=True, amount=5000, attempt_number=1)
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert not result.approved
    assert result.violation_rule == "24h_pre_debit_notice_no_retry"

def test_paused_mandate_nudge_passes():
    event = MandateEvent(decline_code="MANDATE_PAUSED", is_revocable=True, amount=5000, attempt_number=1)
    result = compliance_gate.check(event, proposed_action="SEND_HINGLISH_NUDGE")
    assert result.approved

# --- General pass-through ---

def test_compliant_action_approved():
    event = MandateEvent(mandate_type="UPI_AUTOPAY", attempt_number=1, is_revocable=True, amount=5000, decline_code="BANK_TECHNICAL_DECLINE")
    result = compliance_gate.check(event, proposed_action="RETRY_AFTER_BACKOFF")
    assert result.approved
    assert result.final_action == "RETRY_AFTER_BACKOFF"
    assert result.violation_blocked is False
```

---

## Unit Tests — Tier-2 Schema Validation

File: `tests/unit/test_tier2_schema.py`

```python
def test_pydantic_rejects_out_of_allow_list_action():
    """Tier-2 output with an action outside ALLOWED_ACTIONS must fail validation."""
    with pytest.raises(ValidationError):
        Tier2Result(
            action="INVENT_NEW_ACTION",  # Not in ALLOWED_ACTIONS
            message_hinglish="Test message",
            rationale="Test rationale",
            confidence=0.8
        )

def test_pydantic_accepts_valid_action():
    result = Tier2Result(
        action="ESCALATE_TO_HUMAN",
        message_hinglish="Test",
        rationale="Test",
        confidence=0.9
    )
    assert result.action == "ESCALATE_TO_HUMAN"

def test_tier2_fallback_on_malformed_output():
    """If LLM output is malformed, the system must fall back to ESCALATE_TO_HUMAN."""
    # Simulate a malformed response from Groq
    result = tier2_agent.handle_malformed_response(raw_response="not valid json")
    assert result.action == "ESCALATE_TO_HUMAN"
    assert result.rationale == "tier2_failure"
```

---

## Unit Tests — Audit Log

File: `tests/unit/test_audit.py`

```python
def test_audit_log_is_append_only():
    """The audit log role must not allow UPDATE or DELETE."""
    with pytest.raises(Exception):
        db.execute("UPDATE audit_log SET payload = '{}' WHERE entry_id = 1")

def test_every_mandate_produces_one_audit_entry():
    """Each mandate event in a batch must produce exactly one audit entry."""
    events = generate_batch(size=10)
    process_batch(events)
    audit_entries = db.query("SELECT mandate_id FROM audit_log")
    mandate_ids = [e.mandate_id for e in events]
    for mid in mandate_ids:
        assert audit_entries.count(mid) == 1
```

---

## Integration Tests

File: `tests/integration/test_batch_pipeline.py`

```python
def test_full_batch_tier_split():
    """Full pipeline on 50 records: Tier-1 must resolve 65-75%."""
    events = generate_batch(size=50)
    result = process_batch(events)
    tier1_pct = result.metrics.tier1_resolution_rate
    assert 0.60 <= tier1_pct <= 0.80, f"Tier-1 rate {tier1_pct:.1%} outside expected range"

def test_deliberate_violation_caught_and_not_executed():
    """
    Inject a non-revocable mandate where Tier-2 proposes RETRY_AFTER_BACKOFF.
    The compliance gate must catch it.
    The executed outcome must be ESCALATE_TO_HUMAN, not a retry.
    """
    event = MandateEvent(
        mandate_id="test-non-revocable-001",
        is_revocable=False,
        decline_code="NON_REVOCABLE_HARD_DECLINE",
        amount=45000,
        attempt_number=2
    )
    # Override Tier-2 to propose an illegal action
    with mock.patch("core.tier2_agent.tier2_reason") as mock_tier2:
        mock_tier2.return_value = Tier2Result(action="RETRY_AFTER_BACKOFF", ...)
        result = process_batch([event])
    decision = result.decisions[0]
    assert decision.proposed_action == "RETRY_AFTER_BACKOFF"
    assert decision.compliance_result.violation_blocked is True
    assert decision.final_action == "ESCALATE_TO_HUMAN"
    assert decision.outcome == "escalated"

def test_audit_log_complete_for_batch():
    """Every record in the batch must have exactly one audit entry."""
    events = generate_batch(size=20)
    result = process_batch(events)
    assert len(result.decisions) == 20
    # Verify audit table
    for event in events:
        entries = db.query(audit_log).filter_by(mandate_id=event.mandate_id).all()
        assert len(entries) == 1
```

---

## Held-Out Evaluation Protocol

**When to run:** Day 12 (evaluation day), and once more before recording the demo.

The held-out set was generated and reserved before any rule-writing began. It was never seen during development.

```python
def evaluate_held_out_set():
    held_out = load_held_out_events()   # From data/synthetic_held_out.csv
    results = process_batch(held_out)

    correct = sum(
        1 for r, e in zip(results.decisions, held_out)
        if r.final_action == e.correct_action
    )
    accuracy = correct / len(held_out)

    print(f"Held-out set size: {len(held_out)}")
    print(f"Accuracy: {accuracy:.1%}")
    print(f"Tier-1 resolution rate: {results.metrics.tier1_resolution_rate:.1%}")
    print(f"False escalation rate: {results.metrics.false_escalation_rate:.1%}")
    print(f"Compliance violations caught: {results.metrics.compliance_violations_caught}")
    print(f"Compliance violations executed: {results.metrics.compliance_violations_executed}")

    # This assertion must pass before recording the demo
    assert results.metrics.compliance_violations_executed == 0, \
        "CRITICAL: A compliance violation reached execution. Do not record the demo."
```

---

## Unit Tests — Phase 9 (Auth, Rate Limiter, Tenant Isolation)

### File: `tests/unit/test_auth_middleware.py`

```python
def test_missing_auth_header_returns_401():
    response = client.post("/api/v1/recovery/batch")
    assert response.status_code == 401

def test_invalid_api_key_returns_403():
    response = client.post("/api/v1/recovery/batch",
                           headers={"Authorization": "Bearer bad_key"})
    assert response.status_code == 403

def test_valid_api_key_passes():
    """A properly hashed tenant API key returns 202, not 401/403."""
    # Create tenant with known key, hash it, store in DB
    response = client.post("/api/v1/recovery/batch",
                           headers={"Authorization": f"Bearer {VALID_TEST_KEY}"},
                           files={"file": ("demo.csv", demo_csv_bytes, "text/csv")})
    assert response.status_code == 202

def test_inactive_tenant_returns_403():
    """A valid key for an inactive tenant (is_active=False) must be rejected."""
    response = client.post("/api/v1/recovery/batch",
                           headers={"Authorization": f"Bearer {INACTIVE_TENANT_KEY}"})
    assert response.status_code == 403
```

### File: `tests/unit/test_rate_limiter.py`

```python
def test_rate_limiter_allows_requests_under_budget():
    """Requests within budget are not throttled."""
    limiter = Tier2RateLimiter(redis_client=mock_redis, budget_per_minute=10)
    for _ in range(10):
        allowed = limiter.check_and_record(tenant_id="t_test")
        assert allowed is True

def test_rate_limiter_blocks_at_budget_exhaustion():
    """Request at budget+1 is rejected."""
    limiter = Tier2RateLimiter(redis_client=mock_redis, budget_per_minute=5)
    for _ in range(5):
        limiter.check_and_record(tenant_id="t_test")
    allowed = limiter.check_and_record(tenant_id="t_test")
    assert allowed is False

def test_rate_limiter_downgrades_model():
    """
    When primary budget is exhausted, tier2_agent falls back to llama-3.1-8b-instant.
    If that budget is also exhausted, returns ESCALATE_TO_HUMAN.
    """
    # Exhaust primary budget
    for _ in range(10):
        rate_limiter.check_and_record(tenant_id="t_test")
    # Next call should use fast model
    result = tier2_agent.reason_with_rate_limit(event, tenant_id="t_test")
    assert result.model_used == "llama-3.1-8b-instant" or result.action == "ESCALATE_TO_HUMAN"

def test_tenant_isolation_in_rate_limiter():
    """Budget exhaustion for tenant A must not affect tenant B."""
    for _ in range(10):
        rate_limiter.check_and_record(tenant_id="t_a")
    allowed_b = rate_limiter.check_and_record(tenant_id="t_b")
    assert allowed_b is True
```

### Integration: `tests/integration/test_tenant_pipeline.py`

```python
def test_two_tenants_produce_different_actions_for_same_amount():
    """
    Tenant A: afa_threshold_general=15000 (standard)
    Tenant B: afa_threshold_general=100000 (NPCI-exempt, SIP-only NBFC)
    Same mandate amount=20000:
      - Tenant A: amount > 15000 → SEND_UPI_INTENT_PUSH
      - Tenant B: amount < 100000 → RETRY_AFTER_BACKOFF
    """
    event = MandateEvent(amount=20000, decline_code="AFA_REQUIRED", ...)
    result_a = process_single_with_config(event, tenant_config=TENANT_A_CONFIG)
    result_b = process_single_with_config(event, tenant_config=TENANT_B_CONFIG)
    assert result_a.final_action == "SEND_UPI_INTENT_PUSH"
    assert result_b.final_action != "SEND_UPI_INTENT_PUSH"  # Not blocked for tenant B

def test_tenant_a_cannot_read_tenant_b_decisions():
    """Query with tenant_a credentials must not return tenant_b records."""
    response = client.get("/api/v1/audit",
                          headers={"Authorization": f"Bearer {TENANT_A_KEY}"})
    entries = response.json()["entries"]
    for entry in entries:
        assert entry.get("tenant_id") == TENANT_A_ID
```

---

## Success Metrics and Targets

| Metric | Target | How to Measure |
|---|---|---|
| Recovery rate on held-out batch | Report honestly by category | Run evaluator on the held-out set |
| Tier-1 resolution rate | 65–75% | Count records resolved without Tier-2 |
| Compliance violations caught | > 0 | Proves the gate works; log and display on dashboard |
| Compliance violations executed | 0 | Hard requirement; assert in code before demo recording |
| False escalation rate | < 15% | Cases sent to human unnecessarily |
| Tier-1 latency P95 | < 5ms | Logged per record |
| Tier-2 latency P95 | < 3,000ms | Logged per record |
| Rs. recovered / Rs. at risk | Report honestly | Dashboard front-page stat |

---

## Pre-Demo Verification Checklist

Run all of the following before recording the demo video:

- [ ] `pytest tests/unit/ -v` — all pass, zero failures
- [ ] `pytest tests/unit/test_compliance_gate.py -v` — all pass
- [ ] Held-out evaluation: `compliance_violations_executed == 0` asserted
- [ ] Tier-1 resolution rate logged: confirm 65–75%
- [ ] At least one compliance violation visible in the dashboard (violation caught, not executed)
- [ ] Hinglish message rendered for at least one MANDATE_PAUSED case
- [ ] Human review queue shows the non-revocable EMI case
- [ ] Dashboard Rs. recovered / Rs. at risk numbers are honest (from the held-out run)

---

*Source: Master_Aegis.md §9 Feature 2-4 Testing Requirements, §22, §27 | Last updated: 2026-08-23*
