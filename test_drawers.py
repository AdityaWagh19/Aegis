import json
import time
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

DRAWER_REPORT = {}

def inspect_drawers():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Login as guest
        page.goto("https://aegis-platform.duckdns.org/login")
        page.wait_for_load_state("networkidle")
        guest_btn = page.locator("button:has-text('Continue as guest'), a:has-text('Continue as guest')").first
        if guest_btn.is_visible():
            guest_btn.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

        # Go to batch
        page.goto("https://aegis-platform.duckdns.org/app/batch")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        demo_csv_path = os.path.abspath("data/demo_batch.csv")
        page.locator("input[type='file']").set_input_files(demo_csv_path)

        # Wait for batch completion
        for _ in range(60):
            page.wait_for_timeout(1000)
            if page.locator("text=COMPLIANCE OVERRIDES, text=Decisions").count() > 0:
                break

        page.wait_for_timeout(2000)

        # 1. Inspect MAND-053 drawer
        print("Clicking MAND-053 row in table...")
        mand_53_row = page.locator("tr[aria-label*='MAND-053'], tr:has-text('MAND-053')").first
        mand_53_row.click()
        page.wait_for_timeout(1000)
        
        dialog = page.locator("div[role='dialog']").first
        dialog_text = dialog.inner_text() if dialog.is_visible() else "Dialog not visible"
        print("\n--- MAND-053 DIALOG TEXT ---\n", dialog_text)
        DRAWER_REPORT["mand_053"] = {
            "visible": dialog.is_visible(),
            "dialog_text": dialog_text,
            "has_rationale": "non_revocable" in dialog_text or "ESCALATE" in dialog_text or "hard decline" in dialog_text,
            "has_no_hinglish": "Aapka" not in dialog_text and "Aapki" not in dialog_text and "Hinglish draft" not in dialog_text
        }
        
        # Close via close button
        page.locator("button[aria-label='Close details']").click()
        page.wait_for_timeout(600)

        # 2. Inspect MANDATE_PAUSED row drawer
        print("Clicking MANDATE_PAUSED row in table...")
        paused_row = page.locator("tr:has-text('MANDATE_PAUSED')").first
        paused_row.click()
        page.wait_for_timeout(1000)
        dialog_paused_text = page.locator("div[role='dialog']").first.inner_text() if page.locator("div[role='dialog']").count() > 0 else ""
        print("\n--- MANDATE_PAUSED DIALOG TEXT ---\n", dialog_paused_text)
        DRAWER_REPORT["mandate_paused"] = {
            "visible": page.locator("div[role='dialog']").first.is_visible(),
            "dialog_text": dialog_paused_text,
            "has_hinglish_card": "Hinglish" in dialog_paused_text or "Aapka" in dialog_paused_text or "pending hai" in dialog_paused_text or "MOCK" in dialog_paused_text or "Draft" in dialog_paused_text
        }
        page.locator("button[aria-label='Close details']").click()
        page.wait_for_timeout(600)

        # 3. Inspect Failed outcome row drawer (with Razorpay response JSON)
        print("Clicking Failed outcome row in table...")
        failed_row = page.locator("tr:has-text('failed'), tr:has-text('FAILED')").first
        failed_row.click()
        page.wait_for_timeout(1000)
        dialog_failed = page.locator("div[role='dialog']").first
        dialog_failed_text = dialog_failed.inner_text() if dialog_failed.is_visible() else ""
        print("\n--- FAILED ROW DIALOG TEXT ---\n", dialog_failed_text)
        DRAWER_REPORT["failed_row"] = {
            "visible": dialog_failed.is_visible(),
            "dialog_text": dialog_failed_text,
            "has_razorpay_or_error_json": "error" in dialog_failed_text.lower() or "razorpay" in dialog_failed_text.lower() or "{" in dialog_failed_text or "details" in dialog_failed_text.lower()
        }

        browser.close()

    print("\n--- FINAL DRAWER REPORT ---")
    print(json.dumps(DRAWER_REPORT, indent=2))
    with open("drawer_results.json", "w", encoding="utf-8") as f:
        json.dump(DRAWER_REPORT, f, indent=2)

if __name__ == "__main__":
    inspect_drawers()
