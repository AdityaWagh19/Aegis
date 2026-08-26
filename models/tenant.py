# models/tenant.py
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    master_key = os.getenv("AEGIS_MASTER_ENCRYPTION_KEY")
    if not master_key:
        raise RuntimeError("AEGIS_MASTER_ENCRYPTION_KEY not set.")
    return Fernet(master_key.encode())


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def hash_api_key(api_key: str) -> str:
    """SHA-256 hash of the raw API key. The raw key is only shown at creation time."""
    return hashlib.sha256(api_key.encode()).hexdigest()


class TenantComplianceConfigSchema(BaseModel):
    """Per-tenant compliance thresholds. Overrides compliance_config.yaml defaults."""
    afa_threshold_general: int = 15000
    afa_threshold_sip_insurance: int = 100000
    max_retry_upi_autopay: int = 3
    max_retry_enach: int = 2
    pre_debit_notice_window_hours: int = 24
    tier2_budget_per_minute: int = 10       # Max Groq calls per minute for this tenant


class TenantSchema(BaseModel):
    tenant_id: str
    name: str
    webhook_url: Optional[str] = None
    callback_secret: Optional[str] = None
    is_active: bool = True
    compliance_config: TenantComplianceConfigSchema = TenantComplianceConfigSchema()
