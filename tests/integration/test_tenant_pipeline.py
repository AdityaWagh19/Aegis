# tests/integration/test_tenant_pipeline.py
"""
Integration tests for Phase 9 multi-tenancy.
Verifies that two tenants with different AFA thresholds produce different
actions for the same mandate amount.
"""
import pytest
import unittest.mock as mock
from datetime import datetime, timezone

from models.mandate_event import MandateEvent
from models.recovery_decision import Tier1Result, Tier2Result
from core.config import ComplianceConfig, MaxRetryAttempts, SyntheticDistribution, compliance_config_for_tenant
from models.tenant import TenantComplianceConfigSchema
from core.compliance_gate import ComplianceGate


def _event(**kwargs) -> MandateEvent:
    defaults = dict(
        customer_id="TEST-001", amount=20000, mandate_type="UPI_AUTOPAY",
        product_category="subscription", decline_code="BANK_TECHNICAL_DECLINE",
        days_since_salary_credit=5, prior_bounce_count=0, is_revocable=True,
        attempt_number=1, timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return MandateEvent(**defaults)


TENANT_A_CONFIG = TenantComplianceConfigSchema(
    afa_threshold_general=15000,
    afa_threshold_sip_insurance=100000,
    max_retry_upi_autopay=3,
    max_retry_enach=2,
)

TENANT_B_CONFIG = TenantComplianceConfigSchema(
    afa_threshold_general=100000,
    afa_threshold_sip_insurance=200000,
    max_retry_upi_autopay=3,
    max_retry_enach=2,
)


def test_two_tenants_produce_different_actions_for_same_amount():
    """
    Tenant A: afa_threshold_general=15000 (standard)
    Tenant B: afa_threshold_general=100000 (NPCI-exempt, SIP-only NBFC)
    Same mandate amount=20000:
      - Tenant A: Tier-1 classifies AFA_REQUIRED -> SEND_UPI_INTENT_PUSH
      - Tenant B: Tier-1 classifies as below threshold -> RETRY_AFTER_BACKOFF passes gate
    """
    event = _event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=1)

    cfg_a = compliance_config_for_tenant(TENANT_A_CONFIG)
    cfg_b = compliance_config_for_tenant(TENANT_B_CONFIG)

    gate_a = ComplianceGate(config=cfg_a)
    gate_b = ComplianceGate(config=cfg_b)

    # Both propose RETRY_AFTER_BACKOFF (Tier-1 for BTD within retry limits)
    proposed = "RETRY_AFTER_BACKOFF"

    result_a = gate_a.check(event, proposed)
    result_b = gate_b.check(event, proposed)

    # Tenant A: amount 20000 > 15000 -> AFA rule blocks retry -> redirects to intent push
    assert not result_a.approved
    assert result_a.final_action == "SEND_UPI_INTENT_PUSH"

    # Tenant B: amount 20000 < 100000 -> no AFA violation -> retry approved
    assert result_b.approved
    assert result_b.final_action == "RETRY_AFTER_BACKOFF"


def test_tenant_a_cannot_use_tenant_b_thresholds():
    """Verify that tenant configs are truly independent."""
    cfg_a = compliance_config_for_tenant(TENANT_A_CONFIG)
    cfg_b = compliance_config_for_tenant(TENANT_B_CONFIG)

    assert cfg_a.afa_threshold_general == 15000
    assert cfg_b.afa_threshold_general == 100000
    assert cfg_a.afa_threshold_general != cfg_b.afa_threshold_general


def test_tier1_classify_with_tenant_config():
    """Tier-1 classify() accepts per-tenant config for threshold selection."""
    from core.tier1_engine import classify

    event = _event(decline_code="BANK_TECHNICAL_DECLINE", attempt_number=2)
    cfg_b = compliance_config_for_tenant(TENANT_B_CONFIG)

    # With default config (max UPI=3), attempt=2 < 3 -> retry
    result_default = classify(event)
    assert result_default.action == "RETRY_AFTER_BACKOFF"

    # With tenant config (max UPI=3), same result
    result_b = classify(event, config=cfg_b)
    assert result_b.action == "RETRY_AFTER_BACKOFF"

    # Now with a tenant that has max_retry_upi_autopay=1
    strict_cfg = TenantComplianceConfigSchema(max_retry_upi_autopay=1)
    strict_compliance = compliance_config_for_tenant(strict_cfg)
    result_strict = classify(event, config=strict_compliance)
    assert result_strict.action == "ESCALATE_TO_HUMAN"


def test_compliance_gate_with_tenant_config():
    """ComplianceGate accepts per-tenant config and enforces tenant-specific rules."""
    event = _event(decline_code="AFA_REQUIRED", amount=50000, attempt_number=1)

    # Tenant A (threshold 15000): 50000 > 15000 -> blocks retry
    gate_a = ComplianceGate(config=compliance_config_for_tenant(TENANT_A_CONFIG))
    result_a = gate_a.check(event, "RETRY_AFTER_BACKOFF")
    assert not result_a.approved
    assert result_a.final_action == "SEND_UPI_INTENT_PUSH"

    # Tenant B (threshold 100000): 50000 < 100000 -> allows retry
    gate_b = ComplianceGate(config=compliance_config_for_tenant(TENANT_B_CONFIG))
    result_b = gate_b.check(event, "RETRY_AFTER_BACKOFF")
    assert result_b.approved
    assert result_b.final_action == "RETRY_AFTER_BACKOFF"


def test_razorpay_client_rejects_live_keys():
    """RazorpayClient must reject non-test keys."""
    from services.razorpay_client import RazorpayClient

    with pytest.raises(ValueError, match="rzp_test_"):
        RazorpayClient(key_id="rzp_live_FAKE", key_secret="secret")
