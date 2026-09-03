# services/razorpay_client.py
import os
import asyncio
import logging
from typing import Any

from dotenv import load_dotenv
import razorpay

# Ensure .env is loaded even when this module is used without importing
# services.groq_client first (same pattern as groq_client.py).
load_dotenv()

logger = logging.getLogger(__name__)

_client: razorpay.Client | None = None


def get_razorpay_client() -> razorpay.Client:
    global _client
    if _client is None:
        key_id = os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        if not key_id.startswith("rzp_test_"):
            raise ValueError(
                f"RAZORPAY_KEY_ID must start with 'rzp_test_'. Got: '{key_id[:12]}...'. "
                "Live keys are not permitted."
            )
        _client = razorpay.Client(auth=(key_id, key_secret))
        logger.info("Razorpay test-mode client initialised with key: %s...", key_id[:16])
    return _client


class RazorpayClient:
    """
    Per-tenant Razorpay client wrapper (Phase 9).
    Accepts explicit credentials on initialization for multi-tenancy.
    """
    def __init__(self, key_id: str, key_secret: str):
        if not key_id.startswith("rzp_test_"):
            raise ValueError(
                f"RAZORPAY_KEY_ID must start with 'rzp_test_'. Got: '{key_id[:12]}...'. "
                "Live keys are not permitted."
            )
        self.key_id = key_id
        self.key_secret = key_secret
        self.client = razorpay.Client(auth=(key_id, key_secret))
        logger.info("Razorpay client initialised for key: %s...", key_id[:16])

    async def resume_subscription(self, subscription_id: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.subscription.resume(subscription_id, {"resume_at": "now"})
        )

    async def pause_subscription(self, subscription_id: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.subscription.pause(subscription_id, {"pause_at": "now"})
        )

    async def create_payment_link(
        self,
        amount: int,
        mandate_id: str,
        upi_intent: bool = False,
        customer_name: str | None = None,
        customer_email: str | None = None,
        customer_contact: str | None = None,
    ) -> dict:
        loop = asyncio.get_running_loop()
        # Razorpay test mode rejects upi_link=True with 'UPI Payment Links is not supported in Test Mode'
        # Standard payment links still render UPI checkout, cards, and send emails in test mode.
        is_test_mode = self.key_id.startswith("rzp_test_")
        payload = {
            "amount": amount * 100,
            "currency": "INR",
            "description": f"Payment recovery — {mandate_id}",
            "upi_link": False if is_test_mode else upi_intent,
            "notify": {"sms": False, "email": bool(customer_email)},
            "notes": {"mandate_id": mandate_id, "recovery_type": "UPI_INTENT" if upi_intent else "RENEWAL"},
            "options": {
                "checkout": {
                    "name": "Aegis Mandate Recovery",
                }
            },
        }
        if customer_email or customer_contact:
            payload["customer"] = {
                "name": customer_name or "Valued Customer",
                "email": customer_email or "",
                "contact": customer_contact or "",
            }
        return await loop.run_in_executor(
            None,
            lambda: self.client.payment_link.create(payload)
        )


async def resume_subscription(subscription_id: str) -> dict:
    """RETRY_AFTER_BACKOFF: Resume a paused subscription immediately."""
    client = get_razorpay_client()
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: client.subscription.resume(subscription_id, {"resume_at": "now"})
        )
        logger.info("Resumed subscription %s", subscription_id)
        return result
    except Exception as e:
        logger.error("Failed to resume subscription %s: %s", subscription_id, e)
        raise


async def pause_subscription(subscription_id: str) -> dict:
    """SCHEDULE_POST_SALARY: Pause a subscription to reschedule post-salary."""
    client = get_razorpay_client()
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: client.subscription.pause(subscription_id, {"pause_at": "now"})
        )
        logger.info("Paused subscription %s", subscription_id)
        return result
    except Exception as e:
        logger.error("Failed to pause subscription %s: %s", subscription_id, e)
        raise


async def create_payment_link(
    amount: int,
    mandate_id: str,
    upi_intent: bool = False,
    customer_name: str | None = None,
    customer_email: str | None = None,
    customer_contact: str | None = None,
) -> dict:
    """SEND_UPI_INTENT_PUSH / SEND_MANDATE_RENEWAL_LINK: Create a payment link."""
    client = get_razorpay_client()
    loop = asyncio.get_running_loop()
    # Razorpay test mode rejects upi_link=True with 'UPI Payment Links is not supported in Test Mode'
    # Standard payment links still render UPI checkout, cards, and send emails in test mode.
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    is_test_mode = key_id.startswith("rzp_test_")
    payload = {
        "amount": amount * 100,     # Paise
        "currency": "INR",
        "description": f"Payment recovery — {mandate_id}",
        "upi_link": False if is_test_mode else upi_intent,
        "notify": {"sms": False, "email": bool(customer_email)},
        "notes": {"mandate_id": mandate_id, "recovery_type": "UPI_INTENT" if upi_intent else "RENEWAL"},
        "options": {
            "checkout": {
                "name": "Aegis Mandate Recovery",
            }
        },
    }
    if customer_email or customer_contact:
        payload["customer"] = {
            "name": customer_name or "Valued Customer",
            "email": customer_email or "",
            "contact": customer_contact or "",
        }
    try:
        result = await loop.run_in_executor(
            None,
            lambda: client.payment_link.create(payload)
        )
        logger.info("Created payment link for mandate %s: %s", mandate_id, result.get("short_url"))
        return result
    except Exception as e:
        logger.error("Failed to create payment link for mandate %s: %s", mandate_id, e)
        raise
