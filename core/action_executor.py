# core/action_executor.py
import logging
from models.mandate_event import MandateEvent
from services.razorpay_client import (
    resume_subscription, pause_subscription, create_payment_link
)
from services.mock_notification import notification_service

logger = logging.getLogger(__name__)

# Actions that produce a "mocked" outcome (no Razorpay call)
_MOCK_ACTIONS = {"SEND_HINGLISH_NUDGE", "NO_ACTION_MONITORING", "ESCALATE_TO_HUMAN"}


async def execute(
    event: MandateEvent,
    final_action: str,
    hinglish_message: str | None = None,
) -> tuple[str, dict | None]:
    """
    Execute the approved recovery action.
    Returns (outcome, razorpay_response).
    outcome is one of: "executed", "mocked", "escalated", "failed"
    """
    logger.info("Executing action=%s for mandate_id=%s", final_action, event.mandate_id)

    try:
        if final_action == "RETRY_AFTER_BACKOFF":
            resp = await resume_subscription(event.mandate_id)
            return "executed", resp

        elif final_action == "SCHEDULE_POST_SALARY":
            resp = await pause_subscription(event.mandate_id)
            return "executed", resp

        elif final_action == "SEND_UPI_INTENT_PUSH":
            resp = await create_payment_link(event.amount, event.mandate_id, upi_intent=True)
            if hinglish_message:
                notification_service.send(event.customer_id, hinglish_message)
            return "executed", resp

        elif final_action == "SEND_MANDATE_RENEWAL_LINK":
            resp = await create_payment_link(event.amount, event.mandate_id, upi_intent=False)
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
