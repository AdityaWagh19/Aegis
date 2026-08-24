import json
import time
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

BATCH_AUDIT_REPORT = {}

def inspect_batch_and_audit():
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

        # ----------------------------------------------------
        # D. Batches
        # ----------------------------------------------------
        print("Navigating to /app/batch...")
        page.goto("https://aegis-platform.duckdns.org/app/batch")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        demo_csv_path = os.path.abspath("data/demo_batch.csv")
        file_input = page.locator("input[type='file']")
        
        if file_input.count() > 0:
            print(f"Uploading {demo_csv_path}...")
            file_input.set_input_files(demo_csv_path)
            
            # Watch for changes for up to 90 seconds
            completed = False
            for sec in range(90):
                page.wait_for_timeout(1000)
                body = page.locator("main").inner_text()
                if "OVERRIDE" in body or "MAND-054" in body or "Results" in body or "Rs." in body or "Batch processing complete" in body:
                    print(f"[{sec}s] Batch completed!")
                    completed = True
                    break
                elif sec % 10 == 0:
                    print(f"[{sec}s] Waiting for batch completion...")

            batch_text = page.locator("main").inner_text()
            BATCH_AUDIT_REPORT["batch_completed"] = completed
            BATCH_AUDIT_REPORT["batch_text_snippet"] = batch_text[:800]

            # Metric cards check
            BATCH_AUDIT_REPORT["rs_at_risk"] = "6,35,900" in batch_text or "at risk" in batch_text.lower()
            BATCH_AUDIT_REPORT["violations_executed_zero_check"] = "executed: 0" in batch_text or "0 executed" in batch_text or "executed 0" in batch_text

            # Override section check
            override_section_present = "COMPLIANCE OVERRIDE" in batch_text or "afa_threshold" in batch_text or "MAND-054" in batch_text
            BATCH_AUDIT_REPORT["override_section_present"] = override_section_present
            BATCH_AUDIT_REPORT["mand_054_override_card"] = {
                "present": "MAND-054" in batch_text,
                "has_struck_through_or_rule": "afa_threshold" in batch_text or "Schedule post-salary" in batch_text or "Send UPI intent push" in batch_text
            }

            # Decision table escalated rows
            BATCH_AUDIT_REPORT["escalated_rows"] = {
                "MAND_053": "MAND-053" in batch_text,
                "MAND_055": "MAND-055" in batch_text,
                "MAND_056": "MAND-056" in batch_text
            }

            # Drawer test: MAND-053
            mand_53_el = page.locator("tr", has_text="MAND-053").first
            if mand_53_el.count() > 0 and mand_53_el.is_visible():
                print("Testing MAND-053 drawer...")
                mand_53_el.click()
                page.wait_for_timeout(800)
                drawer_53 = page.locator("div[role='dialog'], aside, .drawer, [class*='drawer']").first.inner_text() if page.locator("div[role='dialog'], aside, .drawer, [class*='drawer']").count() > 0 else ""
                
                BATCH_AUDIT_REPORT["drawer_mand_53"] = {
                    "text_snippet": drawer_53[:400],
                    "rationale_contains_rule_or_escalate": "non_revocable" in drawer_53 or "hard decline" in drawer_53 or "ESCALATE" in drawer_53,
                    "has_no_hinglish": "Aapka" not in drawer_53 and "Aapki" not in drawer_53
                }
                
                # Close via Close button / overlay
                close_btn = page.locator("button[aria-label='Close details'], button:has-text('Close')").first
                if close_btn.is_visible():
                    close_btn.click()
                    page.wait_for_timeout(800)
                
                BATCH_AUDIT_REPORT["drawer_mand_53"]["closed"] = True

            # Drawer test: MANDATE_PAUSED
            paused_el = page.locator("tr", has_text="MANDATE_PAUSED").first
            if paused_el.count() > 0 and paused_el.is_visible():
                print("Testing MANDATE_PAUSED drawer...")
                paused_el.click()
                page.wait_for_timeout(800)
                drawer_paused = page.locator("div[role='dialog'], aside, .drawer, [class*='drawer']").first.inner_text() if page.locator("div[role='dialog'], aside, .drawer, [class*='drawer']").count() > 0 else ""
                
                BATCH_AUDIT_REPORT["drawer_mandate_paused"] = {
                    "text_snippet": drawer_paused[:400],
                    "hinglish_card_visible": "Hinglish" in drawer_paused or "Aapka" in drawer_paused or "Draft" in drawer_paused or "mock" in drawer_paused.lower() or "active" in drawer_paused.lower()
                }
                close_btn = page.locator("button[aria-label='Close details'], button:has-text('Close')").first
                if close_btn.is_visible():
                    close_btn.click()
                    page.wait_for_timeout(800)

            # Drawer test: Failed outcome
            failed_el = page.locator("tr", has_text="failed").first
            if failed_el.count() > 0 and failed_el.is_visible():
                print("Testing Failed outcome drawer...")
                failed_el.click()
                page.wait_for_timeout(800)
                drawer_failed = page.locator("div[role='dialog'], aside, .drawer, [class*='drawer']").first.inner_text() if page.locator("div[role='dialog'], aside, .drawer, [class*='drawer']").count() > 0 else ""
                
                BATCH_AUDIT_REPORT["drawer_failed_outcome"] = {
                    "text_snippet": drawer_failed[:400],
                    "has_razorpay_or_error_json": "error" in drawer_failed.lower() or "razorpay" in drawer_failed.lower() or "{" in drawer_failed
                }
                close_btn = page.locator("button[aria-label='Close details'], button:has-text('Close')").first
                if close_btn.is_visible():
                    close_btn.click()
                    page.wait_for_timeout(800)

            # Test Run another batch
            reset_btn = page.locator("button:has-text('Run another batch'), button:has-text('Upload another'), button:has-text('Upload batch')").first
            if reset_btn.is_visible():
                print("Testing Run another batch...")
                reset_btn.click()
                page.wait_for_timeout(800)
                BATCH_AUDIT_REPORT["run_another_batch_resets_to_uploader"] = page.locator("input[type='file']").count() > 0

        # ----------------------------------------------------
        # E. Audit
        # ----------------------------------------------------
        print("Navigating to /app/audit...")
        page.goto("https://aegis-platform.duckdns.org/app/audit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        BATCH_AUDIT_REPORT["audit_section"] = {}
        total_rows = page.locator("table tbody tr").count()
        BATCH_AUDIT_REPORT["audit_section"]["rows_on_page"] = total_rows

        # Pagination check
        next_btn = page.locator("button:has-text('Next'), a:has-text('Next')").first
        prev_btn = page.locator("button:has-text('Previous'), a:has-text('Prev')").first
        
        pag_works = False
        if next_btn.is_visible() and next_btn.is_enabled():
            next_btn.click()
            page.wait_for_timeout(800)
            if prev_btn.is_visible() and prev_btn.is_enabled():
                prev_btn.click()
                page.wait_for_timeout(800)
                pag_works = True
        BATCH_AUDIT_REPORT["audit_section"]["pagination_works"] = pag_works

        # Search filter MAND-054
        search_inp = page.locator("input[type='text'], input[type='search'], input[placeholder*='Search' i], input[placeholder*='Filter' i]").first
        if search_inp.is_visible():
            print("Filtering MAND-054...")
            search_inp.fill("MAND-054")
            page.wait_for_timeout(1000)
            filtered_table = page.locator("table tbody").inner_text()
            matching_rows = page.locator("table tbody tr").count()
            BATCH_AUDIT_REPORT["audit_section"]["filter_MAND_054"] = {
                "matching_rows_count": matching_rows,
                "found_in_table": "MAND-054" in filtered_table
            }

        browser.close()

    print("\n--- BATCH & AUDIT DETAILED RESULTS ---")
    print(json.dumps(BATCH_AUDIT_REPORT, indent=2))
    with open("batch_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(BATCH_AUDIT_REPORT, f, indent=2)

if __name__ == "__main__":
    inspect_batch_and_audit()
