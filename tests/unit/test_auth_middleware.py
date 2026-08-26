# tests/unit/test_auth_middleware.py
"""
Tests for Phase 9 API key auth middleware.
Tests 401 (missing header), 403 (invalid key), and tenant resolution.
"""
import pytest
import hashlib
import unittest.mock as mock
from datetime import datetime, timezone

from models.mandate_event import MandateEvent
from models.tenant import TenantSchema, TenantComplianceConfigSchema, hash_api_key


def _tenant_schema(tenant_id="t_test123", name="Test NBFC", active=True):
    return TenantSchema(
        tenant_id=tenant_id,
        name=name,
        webhook_url="https://nbfc.example.com/callback",
        is_active=active,
        compliance_config=TenantComplianceConfigSchema(
            afa_threshold_general=15000,
            afa_threshold_sip_insurance=100000,
            max_retry_upi_autopay=3,
            max_retry_enach=2,
            tier2_budget_per_minute=10,
        ),
    )


def test_hash_api_key_deterministic():
    """Same key always produces the same SHA-256 hash."""
    key = "aegis_test_key_123"
    assert hash_api_key(key) == hash_api_key(key)
    assert hash_api_key(key) == hashlib.sha256(key.encode()).hexdigest()


def test_hash_api_key_different_keys():
    """Different keys produce different hashes."""
    assert hash_api_key("key_a") != hash_api_key("key_b")


def test_tenant_schema_defaults():
    """TenantSchema has correct default compliance config."""
    t = _tenant_schema()
    assert t.compliance_config.afa_threshold_general == 15000
    assert t.compliance_config.max_retry_enach == 2
    assert t.compliance_config.tier2_budget_per_minute == 10


def test_tenant_compliance_config_custom():
    """TenantComplianceConfigSchema accepts custom values."""
    cfg = TenantComplianceConfigSchema(
        afa_threshold_general=50000,
        max_retry_enach=5,
        tier2_budget_per_minute=20,
    )
    assert cfg.afa_threshold_general == 50000
    assert cfg.max_retry_enach == 5
    assert cfg.tier2_budget_per_minute == 20


@pytest.mark.asyncio
async def test_auth_missing_header_returns_401():
    """Missing Authorization header returns 401."""
    from api.middleware.auth import get_tenant_from_request
    from fastapi import HTTPException

    request = mock.MagicMock()
    request.headers = {}

    with pytest.raises(HTTPException) as exc_info:
        await get_tenant_from_request(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_invalid_key_returns_403():
    """Invalid API key returns 403 (not cached, hits DB each time)."""
    from api.middleware.auth import get_tenant_from_request
    from fastapi import HTTPException

    request = mock.MagicMock()
    request.headers = {"Authorization": "Bearer invalid_key_that_doesnt_exist"}

    with mock.patch("api.middleware.auth.AsyncSessionLocal") as mock_session:
        mock_db = mock.AsyncMock()
        mock_session.return_value.__aenter__ = mock.AsyncMock(return_value=mock_db)
        mock_db.execute = mock.AsyncMock(return_value=mock.MagicMock(
            scalars=mock.MagicMock(return_value=mock.MagicMock(first=mock.MagicMock(return_value=None)))
        ))

        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_from_request(request)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_valid_key_returns_tenant():
    """Valid API key returns the tenant schema."""
    from api.middleware.auth import get_tenant_from_request

    request = mock.MagicMock()
    raw_key = "aegis_valid_test_key"
    request.headers = {"Authorization": f"Bearer {raw_key}"}

    # Clear cache to force DB lookup
    from api.middleware.auth import _tenant_cache
    _tenant_cache.clear()

    mock_tenant_orm = mock.MagicMock()
    mock_tenant_orm.tenant_id = "t_test123"
    mock_tenant_orm.name = "Test NBFC"
    mock_tenant_orm.webhook_url = "https://nbfc.example.com/callback"
    mock_tenant_orm.is_active = True

    mock_cfg_orm = mock.MagicMock()
    mock_cfg_orm.afa_threshold_general = 15000
    mock_cfg_orm.afa_threshold_sip_insurance = 100000
    mock_cfg_orm.max_retry_upi_autopay = 3
    mock_cfg_orm.max_retry_enach = 2
    mock_cfg_orm.tier2_budget_per_minute = 10

    with mock.patch("api.middleware.auth.AsyncSessionLocal") as mock_session:
        mock_db = mock.AsyncMock()
        mock_session.return_value.__aenter__ = mock.AsyncMock(return_value=mock_db)

        # First execute returns tenant, second returns config
        mock_db.execute = mock.AsyncMock(side_effect=[
            mock.MagicMock(scalars=mock.MagicMock(return_value=mock.MagicMock(first=mock.MagicMock(return_value=mock_tenant_orm)))),
            mock.MagicMock(scalars=mock.MagicMock(return_value=mock.MagicMock(first=mock.MagicMock(return_value=mock_cfg_orm)))),
        ])

        tenant = await get_tenant_from_request(request)
        assert tenant.tenant_id == "t_test123"
        assert tenant.name == "Test NBFC"
        assert tenant.compliance_config.afa_threshold_general == 15000


@pytest.mark.asyncio
async def test_auth_caches_tenant():
    """Second call with same key uses cache (no DB hit)."""
    from api.middleware.auth import get_tenant_from_request, _tenant_cache

    request = mock.MagicMock()
    raw_key = "aegis_cache_test_key"
    request.headers = {"Authorization": f"Bearer {raw_key}"}

    key_hash = hash_api_key(raw_key)
    _tenant_cache[key_hash] = _tenant_schema()

    # Should NOT hit DB — uses cache
    tenant = await get_tenant_from_request(request)
    assert tenant.tenant_id == "t_test123"

    # Cleanup
    del _tenant_cache[key_hash]
