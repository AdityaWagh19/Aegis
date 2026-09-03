import os
import logging
from models.mandate_event import MandateEvent
from services.razorpay_client import (
    resume_subscription, pause_subscription, create_payment_link,
    RazorpayClient
)
from services.mock_notification import notification_service

logger = logging.getLogger(__name__)

# Actions that produce a "mocked" outcome (no Razorpay call)
_MOCK_ACTIONS = {"SEND_HINGLISH_NUDGE", "NO_ACTION_MONITORING", "ESCALATE_TO_HUMAN"}


async def execute(
    event: MandateEvent,
    final_action: str,
    hinglish_message: str | None = None,
    razorpay_client: RazorpayClient | None = None,
) -> tuple[str, dict | None]:
    """
    Execute the approved recovery action.
    Returns (outcome, razorpay_response).
    outcome is one of: "executed", "mocked", "escalated", "failed"

    When razorpay_client is provided (Phase 9 multi-tenancy), uses the per-tenant
    client. Otherwise falls back to the global singleton functions.
    """
    logger.info("Executing action=%s for mandate_id=%s", final_action, event.mandate_id)

    # Resolve per-tenant or global Razorpay functions
    if razorpay_client:
        _resume = razorpay_client.resume_subscription
        _pause = razorpay_client.pause_subscription
        _link = razorpay_client.create_payment_link
    else:
        _resume = resume_subscription
        _pause = pause_subscription
        _link = create_payment_link

    is_real_razorpay = bool(event.mandate_id and event.mandate_id.startswith("sub_"))

    try:
        if final_action == "RETRY_AFTER_BACKOFF":
            if is_real_razorpay:
                resp = await _resume(event.mandate_id)
            else:
                resp = {"status": "resumed", "simulated": True}
            return "executed", resp

        elif final_action == "SCHEDULE_POST_SALARY":
            if is_real_razorpay:
                resp = await _pause(event.mandate_id)
            else:
                resp = {"status": "paused", "simulated": True}
            return "executed", resp

        elif final_action in ("SEND_UPI_INTENT_PUSH", "SEND_MANDATE_RENEWAL_LINK"):
            upi_intent = (final_action == "SEND_UPI_INTENT_PUSH")
            # For the designated live demo customer (CUST-LIVE*), attach presenter details for real email
            is_live_demo = (
                event.customer_id.startswith("CUST-LIVE") or 
                "LIVE" in event.customer_id or
                event.customer_id == "CUST-DEMO"
            )
            if is_live_demo or is_real_razorpay:
                c_name = os.getenv("DEMO_CUSTOMER_NAME", "Valued Customer") if is_live_demo else None
                c_email = os.getenv("DEMO_CUSTOMER_EMAIL") if is_live_demo else None
                c_phone = os.getenv("DEMO_CUSTOMER_PHONE") if is_live_demo else None

                resp = await _link(
                    event.amount,
                    event.mandate_id,
                    upi_intent=upi_intent,
                    customer_name=c_name,
                    customer_email=c_email,
                    customer_contact=c_phone,
                )
            else:
                resp = {"short_url": f"https://rzp.io/i/{event.mandate_id}", "simulated": True}

            if hinglish_message:
                notification_service.send(event.customer_id, hinglish_message)
            return "executed", resp

        elif final_action == "SEND_HINGLISH_NUDGE":
            msg = hinglish_message or "Aapka payment pending hai. Kripya complete karein."
            notification_service.send(event.customer_id, msg)
            return "mocked", None

        elif final_action == "ESCALATE_TO_HUMAN":
            logger.info("Mandate %s escalated to human review", event.mandate_id)
            return "escalated", None

        elif final_action == "NO_ACTION_MONITORING":
            return "mocked", None

        else:
            raise ValueError(f"Unknown final_action: '{final_action}' for mandate_id={event.mandate_id}")

    except ValueError:
        raise
    except Exception as e:
        logger.error("Action execution failed for mandate_id=%s action=%s: %s",
                     event.mandate_id, final_action, e)
        return "failed", {"error": str(e)}
