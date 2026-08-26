# config/loader.py
import yaml
from pathlib import Path
from pydantic import BaseModel


class MaxRetryAttempts(BaseModel):
    UPI_AUTOPAY: int
    ENACH: int


class SyntheticDistribution(BaseModel):
    INSUFFICIENT_FUNDS: float
    BANK_TECHNICAL_DECLINE: float
    MANDATE_PAUSED: float
    AFA_REQUIRED: float
    MANDATE_EXPIRED: float
    NON_REVOCABLE_HARD_DECLINE: float


class ComplianceConfig(BaseModel):
    afa_threshold_general: int
    afa_threshold_sip_insurance: int
    max_retry_attempts: MaxRetryAttempts
    pre_debit_notice_window_hours: int
    synthetic_distribution: SyntheticDistribution


_config: ComplianceConfig | None = None


def load_config(path: str = "compliance_config.yaml") -> ComplianceConfig:
    global _config
    if _config is None:
        with open(Path(path)) as f:
            data = yaml.safe_load(f)
        _config = ComplianceConfig(**data)
    return _config


def get_config() -> ComplianceConfig:
    """FastAPI dependency — returns the loaded config."""
    return load_config()


def compliance_config_for_tenant(tenant_config):
    """
    Converts a TenantComplianceConfigSchema (from DB) to a ComplianceConfig
    compatible with the existing compliance gate and Tier-1 engine.
    ComplianceConfig, MaxRetryAttempts, and load_config are already in scope
    because this function is defined in config/loader.py.
    """
    return ComplianceConfig(
        afa_threshold_general=tenant_config.afa_threshold_general,
        afa_threshold_sip_insurance=tenant_config.afa_threshold_sip_insurance,
        max_retry_attempts=MaxRetryAttempts(
            UPI_AUTOPAY=tenant_config.max_retry_upi_autopay,
            ENACH=tenant_config.max_retry_enach,
        ),
        pre_debit_notice_window_hours=tenant_config.pre_debit_notice_window_hours,
        synthetic_distribution=load_config().synthetic_distribution,  # unchanged
    )
