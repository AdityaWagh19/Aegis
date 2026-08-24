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


async def resume_subscription(subscription_id: str) -> dict:
    """RETRY_AFTER_BACKOFF: Resume a paused subscription immediately."""
    client = get_razorpay_client()
    loop = asyncio.get_running_loop()  # get_running_loop() is safe in async context; get_event_loop() is deprecated in 3.10+, crashes in 3.12
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
    loop = asyncio.get_running_loop()  # get_running_loop() is the correct Python 3.10+ async-safe call
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


async def create_payment_link(amount: int, mandate_id: str, upi_intent: bool = False) -> dict:
    """SEND_UPI_INTENT_PUSH / SEND_MANDATE_RENEWAL_LINK: Create a payment link."""
    client = get_razorpay_client()
    loop = asyncio.get_running_loop()  # get_running_loop() is the correct Python 3.10+ async-safe call
    payload = {
        "amount": amount * 100,     # Paise
        "currency": "INR",
        "description": f"Payment recovery — {mandate_id}",
        "upi_link": upi_intent,
        "notify": {"sms": False, "email": False},
        "notes": {"mandate_id": mandate_id, "recovery_type": "UPI_INTENT" if upi_intent else "RENEWAL"},
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
