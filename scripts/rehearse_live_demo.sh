# scripts/rehearse_live_demo.sh
#!/bin/bash
# Step-by-step rehearsal script for the live recovery demo.
# Run each step in order. Verify output before proceeding to the next.

set -e
echo "=========================================="
echo "  AEGIS LIVE DEMO REHEARSAL"
echo "=========================================="

# Step 1: Verify prerequisites
echo ""
echo "[Step 1] Verifying prerequisites..."
python -c "from dotenv import load_dotenv; load_dotenv(); import os; assert os.getenv('RAZORPAY_KEY_ID','').startswith('rzp_test_'), 'Set RAZORPAY_KEY_ID in .env'; print('  Razorpay test keys OK')"
curl -s https://aegis-platform.duckdns.org/health | grep -q '"ok"' && echo "  API healthy OK" || { echo "  API NOT REACHABLE"; exit 1; }

# Step 2: Seed Razorpay subscriptions
echo ""
echo "[Step 2] Seeding Razorpay subscriptions..."
python scripts/seed_razorpay.py --count 5
echo "  ^ Copy the subscription IDs printed above"

# Step 3: Generate live demo CSV
echo ""
echo "[Step 3] Generate live demo batch CSV..."
echo "  Run: python scripts/make_live_demo_batch.py --subscriptions <sub_1> <sub_2> <sub_3> <sub_4> <sub_5>"
echo "  (Replace with the IDs from Step 2)"

# Step 4: Register webhook
echo ""
echo "[Step 4] Register webhook (if not already registered)..."
echo "  Run: python scripts/register_webhook.py --url https://aegis-platform.duckdns.org/webhooks/razorpay"

# Step 5: Upload batch
echo ""
echo "[Step 5] Upload live demo batch..."
echo "  Run: curl -X POST https://aegis-platform.duckdns.org/api/v1/recovery/batch -F 'file=@data/live_demo_batch.csv'"
echo "  OR upload via the dashboard at https://aegis-platform.duckdns.org/app/batch"

# Step 6: Open payment link on phone
echo ""
echo "[Step 6] LIVE RECOVERY MOMENT..."
echo "  1. Open the Aegis dashboard: https://aegis-platform.duckdns.org/app"
echo "  2. Find the Payment Link URL in the batch results (drawer for the AFA case)"
echo "  3. Open that link on your phone (or browser)"
echo "  4. Complete the test payment using Razorpay test mode"
echo "  5. Watch the dashboard 'Rs. Recovered' counter increment within 10 seconds"
echo "  6. Check the audit trail for the payment_captured entry"

echo ""
echo "=========================================="
echo "  Rehearsal complete. Ready to record!"
echo "=========================================="
