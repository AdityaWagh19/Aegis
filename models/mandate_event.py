# models/mandate_event.py
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator
import uuid


MANDATE_TYPES = Literal["UPI_AUTOPAY", "ENACH"]
PRODUCT_CATEGORIES = Literal["subscription", "loan_emi", "sip", "insurance"]
DECLINE_CODES = Literal[
    "INSUFFICIENT_FUNDS",
    "AFA_REQUIRED",
    "MANDATE_PAUSED",
    "BANK_TECHNICAL_DECLINE",
    "NON_REVOCABLE_HARD_DECLINE",
    "MANDATE_EXPIRED",
    "UNKNOWN",
]

ALLOWED_ACTIONS = [
    "RETRY_AFTER_BACKOFF",
    "SCHEDULE_POST_SALARY",
    "SEND_UPI_INTENT_PUSH",
    "SEND_MANDATE_RENEWAL_LINK",
    "SEND_HINGLISH_NUDGE",
    "ESCALATE_TO_HUMAN",
    "NO_ACTION_MONITORING",
]

RETRY_ACTIONS = ["RETRY_AFTER_BACKOFF", "SCHEDULE_POST_SALARY"]


class MandateEvent(BaseModel):
    mandate_id: Optional[str] = None   # Optional[str]: empty string from CSV also triggers UUID generation
    customer_id: str
    amount: int                            # INR, integer paise-free
    mandate_type: MANDATE_TYPES
    product_category: Optional[PRODUCT_CATEGORIES] = None
    decline_code: str                      # str not Literal — allows UNKNOWN and future codes
    days_since_salary_credit: int          # 0–30
    prior_bounce_count: int                # 0–5
    is_revocable: bool = True
    attempt_number: int = 1               # 1-indexed
    timestamp: datetime
    batch_id: Optional[str] = None
    is_held_out: bool = False
    correct_action: Optional[str] = None  # Ground truth — populated in synthetic data only

    def model_post_init(self, __context) -> None:
        if not self.mandate_id:  # Catches both None and empty string "" from CSV rows
            self.mandate_id = str(uuid.uuid4())
