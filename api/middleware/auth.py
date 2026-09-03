# api/middleware/auth.py
import hashlib
import logging
from fastapi import Request, HTTPException
from sqlalchemy import select
from models.db import AsyncSessionLocal, TenantORM, TenantComplianceConfigORM
from models.tenant import TenantSchema, TenantComplianceConfigSchema

logger = logging.getLogger(__name__)

# In-process tenant cache: api_key_hash -> TenantSchema (TTL via simple dict; use Redis in prod scale)
_tenant_cache: dict[str, TenantSchema | None] = {}


async def get_tenant_from_request(request: Request) -> TenantSchema:
    """
    FastAPI dependency. Validates Authorization: Bearer <api_key> header.
    Sets request.state.tenant for downstream use.
    Raises 401 if header missing, 403 if key invalid or tenant inactive.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or malformed.")

    raw_key = auth_header[len("Bearer "):]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    if key_hash in _tenant_cache:
        tenant = _tenant_cache[key_hash]
        if tenant is None:
            raise HTTPException(status_code=403, detail="Invalid API key.")
        request.state.tenant = tenant
        return tenant

    async with AsyncSessionLocal() as db:
        stmt = (
            select(TenantORM)
            .where(TenantORM.api_key_hash == key_hash)
            .where(TenantORM.is_active == True)  # noqa: E712
        )
        result = await db.execute(stmt)
        tenant_orm = result.scalars().first()

    if not tenant_orm:
        # Do NOT cache negative results. Caching None permanently blacklists the key
        # until process restart, which would block valid keys after a transient DB error.
        # Let invalid key lookups hit the DB each time (they're rare and already hashed).
        logger.warning("Invalid API key presented (hash prefix: %s...)", key_hash[:8])
        raise HTTPException(status_code=403, detail="Invalid API key.")

    # Load compliance config
    async with AsyncSessionLocal() as db:
        cfg_result = await db.execute(
            select(TenantComplianceConfigORM).where(
                TenantComplianceConfigORM.tenant_id == tenant_orm.tenant_id
            )
        )
        cfg_orm = cfg_result.scalars().first()

    compliance_cfg = TenantComplianceConfigSchema(
        afa_threshold_general=cfg_orm.afa_threshold_general if cfg_orm else 15000,
        afa_threshold_sip_insurance=cfg_orm.afa_threshold_sip_insurance if cfg_orm else 100000,
        max_retry_upi_autopay=cfg_orm.max_retry_upi_autopay if cfg_orm else 3,
        max_retry_enach=cfg_orm.max_retry_enach if cfg_orm else 2,
        tier2_budget_per_minute=cfg_orm.tier2_budget_per_minute if cfg_orm else 10,
    )

    tenant = TenantSchema(
        tenant_id=tenant_orm.tenant_id,
        name=tenant_orm.name,
        webhook_url=tenant_orm.webhook_url,
        compliance_config=compliance_cfg,
    )
    _tenant_cache[key_hash] = tenant
    request.state.tenant = tenant
    logger.info("Tenant authenticated: %s (%s)", tenant.name, tenant.tenant_id)
    return tenant
