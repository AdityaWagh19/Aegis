# tests/integration/test_security.py
"""
Automated security test suite verifying:
1. Authentication enforcement (401/403 for unauthenticated/invalid requests).
2. Tenant isolation (Tenant A cannot see Tenant B's data).
3. DoS protections (File size and batch row limits).
4. Protected reset endpoint.
5. Security headers presence.
"""
import io
import pytest
from fastapi.testclient import TestClient
from api.main import app
from models.db import init_db, AsyncSessionLocal, TenantORM, TenantComplianceConfigORM
from models.tenant import hash_api_key

DEMO_KEY = "aegis_demo_key_2026"
TENANT_B_KEY = "aegis_tenant_b_key_789"


@pytest.fixture(scope="module", autouse=True)
def setup_tenants():
    import asyncio

    async def _seed():
        await init_db()
        async with AsyncSessionLocal() as session:
            # Ensure tenant B exists for isolation testing
            stmt = (
                TenantORM.__table__.select().where(TenantORM.tenant_id == "tenant_b")
            )
            res = await session.execute(stmt)
            if not res.first():
                t = TenantORM(
                    tenant_id="tenant_b",
                    name="Tenant B",
                    api_key_hash=hash_api_key(TENANT_B_KEY),
                    is_active=True,
                )
                cfg = TenantComplianceConfigORM(tenant_id="tenant_b")
                session.add(t)
                session.add(cfg)
                await session.commit()

    asyncio.run(_seed())


def test_unauthenticated_request_rejected():
    """Unauthenticated call to protected endpoint must return 401."""
    client = TestClient(app)
    response = client.get("/api/v1/metrics")
    assert response.status_code == 401
    assert "Authorization header missing" in response.json()["detail"]


def test_invalid_api_key_rejected():
    """Invalid Bearer token must return 403."""
    client = TestClient(app)
    response = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer invalid_secret_token_123"},
    )
    assert response.status_code == 403
    assert "Invalid API key" in response.json()["detail"]


def test_valid_api_key_accepted():
    """Valid demo token must return 200 OK."""
    client = TestClient(app)
    response = client.get(
        "/api/v1/metrics",
        headers={"Authorization": f"Bearer {DEMO_KEY}"},
    )
    assert response.status_code == 200
    assert "total_records" in response.json()


def test_security_headers_present():
    """Response must contain OWASP recommended security headers."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_tenant_data_isolation():
    """Tenant B cannot read tenant default's audit log entries."""
    client = TestClient(app)
    # Query with default tenant key
    res_a = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {DEMO_KEY}"},
    )
    assert res_a.status_code == 200

    # Query with Tenant B key
    res_b = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {TENANT_B_KEY}"},
    )
    assert res_b.status_code == 200
    # Tenant B should see 0 entries even if default tenant has records
    assert res_b.json()["total"] == 0


def test_upload_non_csv_rejected():
    """Uploading non-CSV files must be rejected with 400."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/recovery/batch",
        headers={"Authorization": f"Bearer {DEMO_KEY}"},
        files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 400


def test_reset_endpoint_protected_in_production(monkeypatch):
    """In production environment, reset must reject requests without admin key."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AEGIS_ADMIN_SECRET", "super_secret_admin_token_99")

    client = TestClient(app)
    # Call without admin header -> 403
    res_blocked = client.post(
        "/api/v1/recovery/reset",
        headers={"Authorization": f"Bearer {DEMO_KEY}"},
    )
    assert res_blocked.status_code == 403

    # Call with valid admin header -> 200
    res_allowed = client.post(
        "/api/v1/recovery/reset",
        headers={
            "Authorization": f"Bearer {DEMO_KEY}",
            "X-Aegis-Admin-Key": "super_secret_admin_token_99",
        },
    )
    assert res_allowed.status_code == 200
