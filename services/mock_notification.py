# services/mock_notification.py
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)
_LOG_FILE = Path("notification_log.jsonl")


class MockNotificationService:
    """
    Simulates WhatsApp/SMS notification for demo purposes.
    All output is written to notification_log.jsonl and the structured logger.
    No actual messages are sent.
    """

    def send(self, customer_id: str, message: str, channel: str = "whatsapp") -> dict:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id,
            "channel": channel,
            "message": message,
            "status": "MOCKED -- would send in production",
        }
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("[MOCK] %s notification to %s: %.60s...", channel, customer_id, message)
        return entry


# Module-level singleton
notification_service = MockNotificationService()
