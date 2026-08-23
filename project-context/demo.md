# Demo Script — Aegis

> **Status:** Living document. Edit heavily during Days 12–13.
> Freeze after the demo is recorded. Do not modify after recording.

---

## The 5-Minute Demo Flow

Total runtime: 5 minutes. The compliance override moment is the headline — it must be unmissable.

| Time | Beat | What to Show | Narration Guide |
|---|---|---|---|
| 0:00–0:30 | Thesis + the Rs. number | Dashboard front page with Rs. recovered / Rs. at risk | "Indian subscription businesses lose 10–20% of recurring revenue to mandate failures that no global dunning tool understands. Stripe and Churnkey are built for card rails. Aegis is built for UPI Autopay and e-NACH — India-native, compliance-aware, from the ground up." |
| 0:30–1:30 | Tier-1 live | Upload 50+ synthetic failed mandates. Show Tier-1 resolving ~70% in under a second. Failure category table visible on screen. | "We upload a CSV of 52 failed mandates. The Tier-1 deterministic rule engine resolves 37 of them — 71% — in under 200 milliseconds. No LLM call, no cloud round-trip. A lookup table that knows NPCI mandate mechanics." |
| 1:30–2:30 | Tier-2 live | Show Groq (Llama-3.3-70b) reasoning through 2–3 ambiguous cases. JSON output and Hinglish message on screen. | "The remaining 29% are ambiguous — cases where a single decline code isn't enough. These go to our Groq reasoning agent, which produces structured JSON. It can only propose actions from a fixed allow-list. It drafts the Hinglish customer message here." |
| 2:30–3:30 | THE MOMENT | Trigger the non-revocable EMI hard-decline case. Show the ComplianceOverrideCard: Claude proposed RETRY_AFTER_BACKOFF, compliance gate REJECTED it, final action is ESCALATE_TO_HUMAN. | "Watch this case. Mandate MAND-042: loan EMI, second hard decline, non-revocable. The Groq agent proposed a retry. Our compliance gate rejected it. The override is logged. That override is the entire point — no LLM output can execute against a non-revocable mandate after two hard declines. Not configurable. Not bypassable." |
| 3:30–4:30 | Dashboard | Rs. recovered / Rs. at risk front page. Recovery rate by category table. Tier-1 vs Tier-2 split. Compliance violations caught (> 0) vs executed (0). | "The dashboard. Rs. 2,34,500 recovered out of Rs. 5,12,000 at risk — 45.8% recovery rate on a completely fresh batch. Three compliance violations caught by the gate. Zero reached execution." |
| 4:30–5:00 | Close | Static slide or brief narration | "Stripe Smart Retries does not know what a non-revocable e-NACH mandate is. It does not know the AFA threshold. It does not know the 24-hour pre-debit notice rule. Aegis does. The one thing we'd build next: a predictive at-risk scorer — flag mandates before they fail, not after." |

---

## The Compliance Override Moment — Full Detail

This is the demo's centerpiece. Prepare it specifically.

**What to have on screen:**
- The `ComplianceOverrideCard` component rendered for mandate MAND-042
- The compliance violation highlighted in amber/red

**The card should show:**
```
COMPLIANCE OVERRIDE
Mandate: MAND-042 (Loan EMI, 2nd hard decline)
Groq (Tier-2) proposed: RETRY_AFTER_BACKOFF
Compliance Gate: REJECTED
Rule triggered: non_revocable_mandate_no_auto_retry
Final action: ESCALATE_TO_HUMAN
[View full audit entry]
```

**Narration (verbatim option):**
> "Claude proposed a retry. Our compliance gate overrode it. The override is in the audit log — immutable, timestamped, with the rule that triggered it cited. This is the answer to: 'how do you know the AI can't do something it's not supposed to?' The compliance gate is deterministic code, tested with unit tests that prove it cannot be bypassed."

---

## Pre-Demo Checklist

Run all of the following before recording:

### Technical

- [ ] `pytest tests/unit/ -v` — all pass
- [ ] `pytest tests/unit/test_compliance_gate.py -v` — all pass
- [ ] Held-out evaluation run: `compliance_violations_executed == 0` asserted in output
- [ ] Dashboard is accessible at the public URL (not localhost) if recording the live deployment
- [ ] Groq API key is valid and rate limit is not exhausted
- [ ] Razorpay test-mode credentials valid; charge simulator accessible
- [ ] The specific non-revocable case (MAND-042 or equivalent) is in the demo batch

### Screen Setup

- [ ] Browser tab 1: Dashboard front page (Rs. recovered visible)
- [ ] Browser tab 2: Batch upload page (ready to upload demo CSV)
- [ ] Terminal: backend logs visible for narrating real-time decisions
- [ ] Demo CSV prepared: 50+ records with at least one deliberate non-revocable case
- [ ] Screen resolution appropriate for recording (1920x1080 recommended)
- [ ] No personal notifications or windows visible

### Recording

- [ ] Screen recording software running and tested
- [ ] Microphone tested; audio is clear
- [ ] Run through the full 5 minutes at least twice before recording

---

## Submission Checklist

From Appendix B of Master_Aegis.md:

- [ ] Public GitHub repo with a clean README and setup instructions
- [ ] Architecture diagram (use the Mermaid diagram from README.md)
- [ ] 5-minute pitch video following the demo script above — the compliance override moment must be unmissable
- [ ] `project-context/progress.md` renamed or copied to `BUILD_LOG.md` in repo root — with genuine real failures encountered
- [ ] Held-out evaluation metrics reported honestly, including anything unflattering
- [ ] Zero compliance violations in the final executed batch — assert before recording (`compliance_violations_executed == 0`)
- [ ] Unit tests for every compliance gate rule committed to the repo
- [ ] `compliance_config.yaml` committed and readable
- [ ] `.env.example` committed (not `.env`)

---

## Hinglish Message Examples (Seeded to Groq)

For reference during the Tier-2 narration beat:

| Decline Code | Example Hinglish Message |
|---|---|
| `MANDATE_PAUSED` | "Aapka [service_name] subscription abhi bhi active hai! Bas ek click se payment complete karein aur service continue karein." |
| `AFA_REQUIRED` | "Aapki payment ke liye ek-baar approval chahiye. Link pe click karein — 2 minute ka kaam hai!" |
| `INSUFFICIENT_FUNDS` | "Salary aane ke baad aapka payment automatically ho jayega. Koi action ki zaroorat nahi!" |

---

## What to Say if Asked "How Do You Know the Compliance Gate Can't Be Bypassed?"

1. It is a pure function — same inputs always produce the same output.
2. It has unit tests for every rule in isolation, proving each rule activates correctly.
3. It is structurally separate from Tier-1 and Tier-2 — it receives a proposed action; it does not generate one.
4. Its output is the only input to the action executor — nothing downstream reads the proposed action directly.
5. We ran a deliberate violation batch and asserted programmatically that `compliance_violations_executed == 0`.

---

*Source: Master_Aegis.md §28, §29, Appendix B | Last updated: 2026-08-23*
