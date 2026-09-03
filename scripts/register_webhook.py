# scripts/register_webhook.py
"""
Register the Aegis webhook URL in Razorpay (test mode).

Usage:
    python scripts/register_webhook.py --url https://aegis-platform.duckdns.org/webhooks/razorpay
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os
import razorpay


def main(url: str):
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_id.startswith("rzp_test_"):
        print("ERROR: RAZORPAY_KEY_ID must be a test-mode key")
        sys.exit(1)

    client = razorpay.Client(auth=(key_id, key_secret))

    webhook_payload = {
        "url": url,
        "active": True,
        "events": {
            "payment.failed": True,
            "payment.captured": True,
            "subscription.charged": True,
            "subscription.pending": True,
            "subscription.activated": True,
        },
    }
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if webhook_secret:
        webhook_payload["secret"] = webhook_secret

    webhook = client.webhook.create(webhook_payload)

    print(f"Webhook registered successfully!")
    print(f"  ID:     {webhook['id']}")
    print(f"  URL:    {webhook['url']}")
    print(f"  Active: {webhook['active']}")
    print(f"  Events: {', '.join(k for k, v in webhook['events'].items() if v)}")
    print(f"\nTest with: curl -X POST {url} (expect 403 without valid HMAC)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Public HTTPS webhook URL")
    args = parser.parse_args()
    main(args.url)
