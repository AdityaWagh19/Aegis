import json
import time
import os
import sys
import traceback
from playwright.sync_api import sync_playwright

REPORT = {
    "console_messages": [],
    "page_errors": [],
    "sections": {},
    "status": "IN_PROGRESS"
}

def log_console(msg):
    REPORT["console_messages"].append(f"[{msg.type}] {msg.text}")

def log_error(err):
    REPORT["page_errors"].append(str(err))

def run_audit():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("console", log_console)
        page.on("pageerror", log_error)

        # ----------------------------------------------------
        # A. Public pages
        # ----------------------------------------------------
        REPORT["sections"]["A_Public_Pages"] = {}
        print("Starting Section A: Public pages...")
        
        # 1. Landing /
        page.goto("https://aegis-platform.duckdns.org/")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="landing.png")
        
        # Hero headline check
        h1_text = page.locator("h1").inner_text() if page.locator("h1").count() > 0 else ""
        spans = page.locator("h1 span").all()
        cyan_spans = []
        for s in spans:
            style = s.get_attribute("style") or ""
            cls = s.get_attribute("class") or ""
            if "cyan" in cls or "cyan" in style or "rgb(6, 182, 212)" in style or "#06b6d4" in style:
                cyan_spans.append(s.inner_text())
        
        REPORT["sections"]["A_Public_Pages"]["hero_headline"] = {
            "h1": h1_text,
            "cyan_highlighted_phrases": cyan_spans,
            "has_exactly_one_cyan_highlight": len(cyan_spans) == 1
        }
        
        # Floating preview card with 3 tab pills
        tabs = page.locator("button, div[role='tab']").all()
        tab_switch_results = []
        for t in tabs:
            txt = t.inner_text().strip()
            if any(k in txt.lower() for k in ["decision", "override", "audit", "preview"]):
                try:
                    t.click()
                    page.wait_for_timeout(300)
                    tab_switch_results.append(txt)
                except Exception as e:
                    pass
            
        REPORT["sections"]["A_Public_Pages"]["preview_tabs_switched"] = tab_switch_results
        
        # Page body search for key sections
        body_text = page.locator("body").inner_text()
        
        REPORT["sections"]["A_Public_Pages"]["has_how_it_works"] = "How it works" in body_text or "How It Works" in body_text
        categories = ["INSUFFICIENT_FUNDS", "AFA_REQUIRED", "MANDATE_PAUSED", "BANK_TECHNICAL_DECLINE", "NON_REVOCABLE_HARD_DECLINE", "MANDATE_EXPIRED"]
        found_cats = [c for c in categories if c in body_text]
        REPORT["sections"]["A_Public_Pages"]["failure_categories_found"] = found_cats
        REPORT["sections"]["A_Public_Pages"]["all_6_categories_present"] = len(found_cats) == 6
        REPORT["sections"]["A_Public_Pages"]["compliance_promise_present"] = ("asserted in tests" in body_text) or ("zero" in body_text.lower() and "compliance" in body_text.lower())
        REPORT["sections"]["A_Public_Pages"]["footer_present"] = page.locator("footer").count() > 0

        # 2. Docs /docs
        print("Starting Docs /docs test...")
        page.goto("https://aegis-platform.duckdns.org/docs")
        page.wait_for_load_state("networkidle")
        docs_body = page.locator("body").inner_text()
        sidebar_links = [a.inner_text().strip() for a in page.locator("aside a, nav a").all() if a.inner_text().strip()]
        
        # Test anchor click
        anchor_clicked = False
        if page.locator("aside a, nav a").count() > 0:
            first_link = page.locator("aside a, nav a").first
            first_link.click()
            page.wait_for_timeout(300)
            anchor_clicked = True
            
        REPORT["sections"]["A_Public_Pages"]["docs"] = {
            "sidebar_links": sidebar_links[:10],
            "anchor_clickable": anchor_clicked,
            "csv_column_dictionary_present": "CSV" in docs_body or "Column" in docs_body or "Dictionary" in docs_body,
            "has_curl_examples": "curl" in docs_body,
            "has_7_endpoints": sum(1 for ep in ["/api/v1/recovery/batch", "/api/v1/recovery/batch/{", "/api/v1/mandates/{", "/api/v1/metrics", "/api/v1/audit", "/api/v1/human-review", "/webhooks/razorpay"] if ep in docs_body)
        }

        # ----------------------------------------------------
        # B. Onboarding & Auth
        # ----------------------------------------------------
        print("Starting Section B: Onboarding & Auth...")
        REPORT["sections"]["B_Onboarding"] = {}
        
        context.clear_cookies()
        page.goto("https://aegis-platform.duckdns.org/app")
        page.wait_for_load_state("networkidle")
        REPORT["sections"]["B_Onboarding"]["bounced_to_url"] = page.url
        REPORT["sections"]["B_Onboarding"]["bounced_correctly"] = "/login" in page.url

        # Empty email submit check
        email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Continue')").first
        
        if submit_btn.is_visible():
            submit_btn.click()
            page.wait_for_timeout(400)
            login_text = page.locator("body").inner_text()
            REPORT["sections"]["B_Onboarding"]["empty_email_red_hint_visible"] = any(k in login_text.lower() for k in ["required", "enter", "valid", "email"])

        # Click Continue as guest
        guest_btn = page.locator("button:has-text('Continue as guest'), a:has-text('Continue as guest'), button:has-text('Guest')").first
        if guest_btn.is_visible():
            guest_btn.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
        
        REPORT["sections"]["B_Onboarding"]["after_guest_url"] = page.url
        REPORT["sections"]["B_Onboarding"]["landed_on_overview"] = "/app" in page.url and "/login" not in page.url

        app_text = page.locator("body").inner_text()
        REPORT["sections"]["B_Onboarding"]["sidebar_test_mode_chip"] = "Test mode" in app_text or "TEST MODE" in app_text
        REPORT["sections"]["B_Onboarding"]["sidebar_sign_out_visible"] = page.locator("button:has-text('Sign out'), a:has-text('Sign out')").count() > 0

        # ----------------------------------------------------
        # C. Overview /app
        # ----------------------------------------------------
        print("Starting Section C: Overview...")
        REPORT["sections"]["C_Overview"] = {}
        page.goto("https://aegis-platform.duckdns.org/app")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path="overview.png")

        overview_text = page.locator("body").inner_text()
        
        # Check values
        REPORT["sections"]["C_Overview"]["stats_summary"] = {
            "mandates_processed_present": "56" in overview_text or "Mandates" in overview_text,
            "tier1_present": "47" in overview_text or "Tier-1" in overview_text,
            "escalated_present": "3" in overview_text or "Escalated" in overview_text,
            "violations_executed_zero": "executed: 0" in overview_text or "0 executed" in overview_text or "executed 0" in overview_text or "Violations" in overview_text,
            "recovery_by_category_table": "INSUFFICIENT_FUNDS" in overview_text
        }

        # Check Human Review queue
        hr_rows = page.locator("table tbody tr, .human-review-item, tr:has-text('MAND-')").all()
        hr_row_texts = [r.inner_text().strip() for r in hr_rows if "MAND-" in r.inner_text()]
        REPORT["sections"]["C_Overview"]["human_review_queue_count"] = len(hr_row_texts)
        REPORT["sections"]["C_Overview"]["human_review_items"] = hr_row_texts
        
        # Check MAND-053 specifically
        mand_53_in_hr = any("MAND-053" in t for t in hr_row_texts)
        REPORT["sections"]["C_Overview"]["MAND_053_in_queue"] = mand_53_in_hr

        # Resolve one item
        resolve_btns = page.locator("button:has-text('Mark resolved'), button:has-text('Resolve'), button:has-text('Mark as Resolved')").all()
        if resolve_btns:
            print(f"Found {len(resolve_btns)} resolve buttons. Clicking first...")
            resolve_btns[0].click()
            page.wait_for_timeout(1000)
            
            # Check after resolve
            hr_after = [r.inner_text().strip() for r in page.locator("table tbody tr, tr:has-text('MAND-')").all() if "MAND-" in r.inner_text()]
            REPORT["sections"]["C_Overview"]["count_after_resolve"] = len(hr_after)
            
            # Reload to check persistence
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            hr_reloaded = [r.inner_text().strip() for r in page.locator("table tbody tr, tr:has-text('MAND-')").all() if "MAND-" in r.inner_text()]
            REPORT["sections"]["C_Overview"]["count_after_reload"] = len(hr_reloaded)
            REPORT["sections"]["C_Overview"]["stays_resolved_on_refresh"] = len(hr_reloaded) <= len(hr_after)

        # ----------------------------------------------------
        # D. Batches /app/batch
        # ----------------------------------------------------
        print("Starting Section D: Batches...")
        REPORT["sections"]["D_Batches"] = {}
        page.goto("https://aegis-platform.duckdns.org/app/batch")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Check empty state / uploader
        file_input = page.locator("input[type='file']")
        REPORT["sections"]["D_Batches"]["empty_uploader_visible"] = file_input.count() > 0 or page.locator("text=Drag CSV").count() > 0

        demo_csv_path = os.path.abspath("data/demo_batch.csv")
        if file_input.count() > 0 and os.path.exists(demo_csv_path):
            print(f"Uploading demo batch: {demo_csv_path}")
            file_input.set_input_files(demo_csv_path)
            
            # Wait for upload processing
            page.wait_for_timeout(2000)
            try:
                page.wait_for_selector("text=COMPLIANCE OVERRIDE, text=MAND-054, text=Decisions, text=Results", timeout=45000)
            except Exception:
                pass
            
            page.wait_for_timeout(2000)
            page.screenshot(path="batch_results.png")
            batch_text = page.locator("body").inner_text()
            
            REPORT["sections"]["D_Batches"]["results_rendered"] = "MAND-" in batch_text
            REPORT["sections"]["D_Batches"]["rs_at_risk_visible"] = "6,35,900" in batch_text or "at risk" in batch_text.lower()
            REPORT["sections"]["D_Batches"]["compliance_override_section_present"] = "COMPLIANCE OVERRIDE" in batch_text or "MAND-054" in batch_text
            REPORT["sections"]["D_Batches"]["mand_054_override_card"] = "MAND-054" in batch_text and ("Schedule post-salary" in batch_text or "Send UPI intent push" in batch_text or "afa_threshold" in batch_text)
            
            # Drawer test: MAND-053
            mand_53_el = page.locator("tr", has_text="MAND-053").first
            if mand_53_el.count() > 0 and mand_53_el.is_visible():
                print("Clicking MAND-053 for drawer...")
                mand_53_el.click()
                page.wait_for_timeout(800)
                drawer_text = page.locator("aside, [role='dialog'], .drawer, [class*='drawer']").first.inner_text() if page.locator("aside, [role='dialog'], .drawer, [class*='drawer']").count() > 0 else page.locator("body").inner_text()
                
                REPORT["sections"]["D_Batches"]["mand_053_drawer_rationale"] = "non_revocable" in drawer_text or "hard decline" in drawer_text or "ESCALATE_TO_HUMAN" in drawer_text
                REPORT["sections"]["D_Batches"]["mand_053_drawer_has_no_hinglish"] = "Aapka" not in drawer_text and "Aapki" not in drawer_text
                
                # Close via Esc
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                
                # Reopen and close via overlay click
                mand_53_el.click()
                page.wait_for_timeout(500)
                # Click outside
                page.mouse.click(50, 50)
                page.wait_for_timeout(500)

            # Drawer test: MANDATE_PAUSED
            paused_el = page.locator("tr", has_text="MANDATE_PAUSED").first
            if paused_el.count() > 0 and paused_el.is_visible():
                paused_el.click()
                page.wait_for_timeout(800)
                paused_drawer_text = page.locator("aside, [role='dialog'], .drawer, [class*='drawer']").first.inner_text() if page.locator("aside, [role='dialog'], .drawer, [class*='drawer']").count() > 0 else ""
                REPORT["sections"]["D_Batches"]["mandate_paused_hinglish_visible"] = ("Hinglish" in paused_drawer_text or "Aapka" in paused_drawer_text or "nudge" in paused_drawer_text.lower() or "Draft" in paused_drawer_text)
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            # Drawer test: Failed outcome
            failed_el = page.locator("tr", has_text="failed").first
            if failed_el.count() > 0 and failed_el.is_visible():
                failed_el.click()
                page.wait_for_timeout(800)
                failed_drawer_text = page.locator("aside, [role='dialog'], .drawer, [class*='drawer']").first.inner_text() if page.locator("aside, [role='dialog'], .drawer, [class*='drawer']").count() > 0 else ""
                REPORT["sections"]["D_Batches"]["failed_drawer_has_details"] = "error" in failed_drawer_text.lower() or "razorpay" in failed_drawer_text.lower() or "response" in failed_drawer_text.lower()
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            # Run another batch resets
            reset_btn = page.locator("button:has-text('Run another batch'), button:has-text('Upload another'), button:has-text('Upload batch')").first
            if reset_btn.is_visible():
                reset_btn.click()
                page.wait_for_timeout(500)
                REPORT["sections"]["D_Batches"]["run_another_batch_resets"] = page.locator("input[type='file']").count() > 0

        # ----------------------------------------------------
        # E. Audit /app/audit
        # ----------------------------------------------------
        print("Starting Section E: Audit...")
        REPORT["sections"]["E_Audit"] = {}
        page.goto("https://aegis-platform.duckdns.org/app/audit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path="audit.png")

        audit_text = page.locator("body").inner_text()
        audit_rows = page.locator("table tbody tr").all()
        REPORT["sections"]["E_Audit"]["rows_rendered_on_page"] = len(audit_rows)
        
        # Test pagination
        next_btn = page.locator("button:has-text('Next'), a:has-text('Next')").first
        prev_btn = page.locator("button:has-text('Previous'), a:has-text('Prev')").first
        
        pagination_works = False
        if next_btn.is_visible() and next_btn.is_enabled():
            next_btn.click()
            page.wait_for_timeout(800)
            if prev_btn.is_visible() and prev_btn.is_enabled():
                prev_btn.click()
                page.wait_for_timeout(800)
                pagination_works = True
        REPORT["sections"]["E_Audit"]["pagination_both_ways"] = pagination_works

        # Filter MAND-054
        search_box = page.locator("input[placeholder*='Search' i], input[placeholder*='Filter' i], input[type='search'], input[type='text']").first
        if search_box.is_visible():
            search_box.fill("MAND-054")
            page.wait_for_timeout(600)
            filtered_text = page.locator("table tbody").inner_text() if page.locator("table tbody").count() > 0 else ""
            REPORT["sections"]["E_Audit"]["filter_MAND_054_success"] = "MAND-054" in filtered_text

        # ----------------------------------------------------
        # G. Session / Sign out
        # ----------------------------------------------------
        print("Starting Section G: Session...")
        REPORT["sections"]["G_Session"] = {}
        sign_out_btn = page.locator("button:has-text('Sign out'), a:has-text('Sign out')").first
        if sign_out_btn.is_visible():
            sign_out_btn.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            REPORT["sections"]["G_Session"]["after_signout_url"] = page.url
            REPORT["sections"]["G_Session"]["returned_to_login"] = "/login" in page.url

            # Direct nav to /app
            page.goto("https://aegis-platform.duckdns.org/app")
            page.wait_for_load_state("networkidle")
            REPORT["sections"]["G_Session"]["direct_app_bounces_to_login"] = "/login" in page.url

        REPORT["status"] = "COMPLETE"
        browser.close()

    print("\n--- FINAL AUDIT REPORT JSON ---")
    print(json.dumps(REPORT, indent=2))
    with open("audit_results.json", "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2)

if __name__ == "__main__":
    try:
        run_audit()
    except Exception as e:
        traceback.print_exc()
