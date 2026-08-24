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
