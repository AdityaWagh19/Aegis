import { useEffect } from 'react';
import MarketingLayout from '../layouts/MarketingLayout';

const NAV = [
  ['overview', 'Overview'],
  ['architecture', 'Two-tier architecture'],
  ['compliance', 'Compliance rules'],
  ['csv-format', 'CSV upload format'],
  ['api', 'API reference'],
  ['actions', 'Action allow-list'],
  ['auth', 'Authentication'],
  ['multi-tenancy', 'Multi-tenancy'],
  ['webhooks', 'Webhook events'],
  ['rate-limiting', 'Rate limiting'],
  ['metrics-api', 'Metrics (Prometheus)'],
] as const;

function Endpoint({ method, path, children }: { method: string; path: string; children: React.ReactNode }) {
  return (
    <div className="mt-16">
      <p className="flex items-center gap-8 flex-wrap">
        <span
          className={`rounded-full px-12 py-2 text-[11px] font-medium ${
            method === 'GET' ? 'bg-info-tint text-info' : 'bg-success-tint text-success'
          }`}
        >
          {method}
        </span>
        <code className="text-[13px] text-ink-black">{path}</code>
      </p>
      <div className="mt-8 text-[14px] text-warm-gray">{children}</div>
    </div>
  );
}

function Curl({ children }: { children: string }) {
  return (
    <pre className="mt-8 bg-soot text-pure-white rounded-lg p-16 text-[13px] overflow-x-auto whitespace-pre-wrap">
      {children}
    </pre>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="mt-8 bg-soot text-pure-white rounded-lg p-16 text-[13px] overflow-x-auto whitespace-pre-wrap">
      {children}
    </pre>
  );
}

export default function Docs() {
  useEffect(() => {
    document.title = 'Docs · Aegis';
  }, []);

  return (
    <MarketingLayout>
      <div className="mx-auto max-w-[1200px] px-16 py-48 md:py-64 pb-96 md:pb-160 grid lg:grid-cols-[200px_1fr] gap-48">
        {/* Desktop anchor sidebar */}
        <aside className="hidden lg:block">
          <nav className="sticky top-48 flex flex-col gap-4 border-l border-stone-border">
            {NAV.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="-ml-px pl-16 py-4 text-[13px] text-warm-gray hover:text-ink-black border-l border-transparent hover:border-stone-muted transition-colors"
              >
                {label}
              </a>
            ))}
          </nav>
        </aside>

        <article className="max-w-[720px] flex flex-col gap-32">
          {/* Mobile table of contents — visible below lg breakpoint */}
          <details className="lg:hidden rounded-lg border border-stone-border bg-pure-white overflow-hidden">
            <summary className="px-16 py-12 text-[13px] font-medium text-ink-black cursor-pointer select-none flex items-center justify-between">
              On this page
              <span aria-hidden="true" className="text-warm-gray text-[10px]">▼</span>
            </summary>
            <nav className="px-16 pb-12 flex flex-col gap-4 border-t border-stone-border pt-8">
              {NAV.map(([id, label]) => (
                <a
                  key={id}
                  href={`#${id}`}
                  className="py-4 text-[13px] text-warm-gray hover:text-ink-black transition-colors"
                >
                  {label}
                </a>
              ))}
            </nav>
          </details>

          <header>
            <h1 className="font-roobert font-normal text-heading-sm leading-heading-sm tracking-heading-sm text-ink-black">
              Aegis documentation
            </h1>
            <p className="mt-12 text-body-lg leading-body-lg text-warm-gray">
              Everything needed to run batches against the API and understand every action it can
              take.
            </p>
            <div className="mt-16 rounded-lg border border-stone-border bg-pure-white p-16 text-[13px]">
              <p className="font-medium text-ink-black mb-4">Base URLs</p>
              <p className="text-warm-gray">
                Production: <code className="text-ink-black">https://aegis-platform.duckdns.org</code>
              </p>
              <p className="text-warm-gray mt-4">
                Local development: <code className="text-ink-black">http://localhost:8000</code>
              </p>
            </div>
          </header>

          <section id="overview" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Overview</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Aegis ingests failed UPI Autopay / e-NACH mandate events, diagnoses the root cause, and
              executes the one compliant recovery action per mandate — with an append-only audit
              trail for every decision.
            </p>
            <p className="mt-8 text-[14px] text-warm-gray">
              The system is designed for NBFCs, subscription SaaS companies, and any business
              collecting recurring payments on Indian payment rails. It runs as a sidecar alongside
              your existing payment gateway integration.
            </p>
          </section>

          <section id="architecture" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Two-tier architecture</h2>
            <ol className="mt-8 list-decimal pl-24 text-[14px] text-warm-gray space-y-8">
              <li>
                <strong className="text-ink-black">Tier-1 rule engine</strong> — deterministic lookup
                with contextual overrides; resolves ~65–80% of cases in microseconds.
              </li>
              <li>
                <strong className="text-ink-black">Tier-2 Groq agent</strong> — ambiguous cases go to
                an LLM constrained to a fixed seven-action allow-list with structured tool-call
                output.
              </li>
              <li>
                <strong className="text-ink-black">Compliance gate</strong> — a pure function every
                proposed action must pass. It cannot be bypassed by any LLM output or configuration.
              </li>
              <li>
                <strong className="text-ink-black">Executor + audit</strong> — approved actions run
                against Razorpay test-mode APIs; each decision writes exactly one append-only audit
                entry.
              </li>
            </ol>
          </section>

          <section id="compliance" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Compliance rules enforced by the gate</h2>
            <div className="mt-8 overflow-x-auto rounded-lg border border-stone-border">
              <table className="w-full text-[13px] bg-pure-white">
                <thead>
                  <tr className="border-b border-stone-border">
                    {['Rule', 'Trigger', 'Redirect to'].map(h => (
                      <th key={h} scope="col" className="text-left px-12 py-8 font-medium text-warm-gray uppercase text-caption tracking-[0.025em]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['Non-revocable mandate', 'is_revocable=false + NON_REVOCABLE_HARD_DECLINE', 'ESCALATE_TO_HUMAN'],
                    ['Max retry cap', 'attempt_number ≥ max (UPI: 3 · ENACH: 2)', 'ESCALATE_TO_HUMAN'],
                    ['AFA threshold', 'amount > Rs. 15,000 (Rs. 1,00,000 SIP/insurance)', 'SEND_UPI_INTENT_PUSH'],
                    ['24h pre-debit notice', 'decline_code = MANDATE_PAUSED', 'SEND_HINGLISH_NUDGE'],
                  ].map(([r, t, a]) => (
                    <tr key={r} className="border-b border-stone-border last:border-b-0">
                      <td className="px-12 py-8 text-ink-black">{r}</td>
                      <td className="px-12 py-8 text-warm-gray">{t}</td>
                      <td className="px-12 py-8 font-mono text-[12px] text-cyan-edge">{a}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="csv-format" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">CSV upload format</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              One header row plus one row per failed mandate. Required columns:
            </p>
            <div className="mt-8 overflow-x-auto rounded-lg border border-stone-border">
              <table className="w-full text-[13px] bg-pure-white">
                <thead>
                  <tr className="border-b border-stone-border">
                    {['Column', 'Type', 'Notes'].map(h => (
                      <th key={h} scope="col" className="text-left px-12 py-8 font-medium text-warm-gray uppercase text-caption tracking-[0.025em]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['mandate_id', 'string', 'optional — UUID generated when empty'],
                    ['customer_id', 'string', 'required'],
                    ['amount', 'integer', 'INR rupees'],
                    ['mandate_type', 'enum', 'UPI_AUTOPAY | ENACH'],
                    ['product_category', 'enum', 'subscription | loan_emi | sip | insurance'],
                    ['decline_code', 'string', 'one of the six categories, or anything → routed to Tier-2 as unknown'],
                    ['days_since_salary_credit', 'integer', '0–30'],
                    ['prior_bounce_count', 'integer', '0–5'],
                    ['is_revocable', 'bool', 'true/false'],
                    ['attempt_number', 'integer', '1-indexed'],
                    ['timestamp', 'ISO datetime', 'e.g. 2026-08-24T10:00:00+05:30'],
                  ].map(([c, t, n]) => (
                    <tr key={c} className="border-b border-stone-border last:border-b-0">
                      <td className="px-12 py-8 font-mono text-[12px] text-ink-black">{c}</td>
                      <td className="px-12 py-8 text-warm-gray">{t}</td>
                      <td className="px-12 py-8 text-warm-gray">{n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="api" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">API reference</h2>

            <Endpoint method="POST" path="/api/v1/recovery/batch">
              Upload a mandates CSV; the batch runs inline and returns batch metrics.
              <Curl>{`curl -X POST https://aegis-platform.duckdns.org/api/v1/recovery/batch \\\n  -F "file=@mandates.csv"`}</Curl>
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/recovery/batch/{batch_id}">
              Full decisions for a processed batch (available for the lifetime of the server process).
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/metrics">
              All-time aggregates: tier split, executed/escalated counts, violations caught vs
              executed, Rs. recovered, Rs. at risk, recovery rate by category, auto-resolution rate,
              analyst hours saved.
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/audit?page=1&page_size=50">
              Paginated append-only audit trail.
              <Curl>{`curl "https://aegis-platform.duckdns.org/api/v1/audit?page=1&page_size=10"`}</Curl>
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/mandates/{mandate_id}">
              First audit entry for a single mandate — the full decision record.
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/human-review">
              Unresolved escalated mandates. Resolve one:
              <Curl>{`curl -X POST https://aegis-platform.duckdns.org/api/v1/human-review/{review_id}/resolve`}</Curl>
            </Endpoint>

            <Endpoint method="POST" path="/webhooks/razorpay">
              Subscription lifecycle webhooks. Requests must carry{' '}
              <code className="text-[12px]">X-Razorpay-Signature</code> — HMAC-SHA256 of the raw body
              using RAZORPAY_WEBHOOK_SECRET. Unsigned requests get <strong>403</strong>.
            </Endpoint>

            <Endpoint method="GET" path="/health">
              Health check. Returns <code>{`{"status":"ok","service":"aegis"}`}</code>.
            </Endpoint>
          </section>

          <section id="actions" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Action allow-list</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Tier-2 can propose only these seven actions — Pydantic rejects anything else at parse
              time:
            </p>
            <div className="mt-8 rounded-lg border border-stone-border bg-pure-white p-16">
              <ul className="grid sm:grid-cols-2 gap-x-24 gap-y-4">
                {[
                  'RETRY_AFTER_BACKOFF',
                  'SCHEDULE_POST_SALARY',
                  'SEND_UPI_INTENT_PUSH',
                  'SEND_MANDATE_RENEWAL_LINK',
                  'SEND_HINGLISH_NUDGE',
                  'ESCALATE_TO_HUMAN',
                  'NO_ACTION_MONITORING',
                ].map(a => (
                  <li key={a} className="font-mono text-[12px] text-ink-black py-2">{a}</li>
                ))}
              </ul>
            </div>
          </section>

          <section id="auth" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Authentication</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              API routes accept a Bearer token in the Authorization header. Keys are SHA-256 hashed
              at rest — the raw key is only shown at creation time.
            </p>
            <CodeBlock>{`curl -H "Authorization: Bearer aegis_YOUR_KEY" \\\n  https://aegis-platform.duckdns.org/api/v1/metrics`}</CodeBlock>
            <div className="mt-8 overflow-x-auto rounded-lg border border-stone-border">
              <table className="w-full text-[13px] bg-pure-white">
                <thead>
                  <tr className="border-b border-stone-border">
                    {['Scenario', 'Response'].map(h => (
                      <th key={h} scope="col" className="text-left px-12 py-8 font-medium text-warm-gray uppercase text-caption tracking-[0.025em]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-stone-border">
                    <td className="px-12 py-8 text-warm-gray">No Authorization header</td>
                    <td className="px-12 py-8 font-mono text-[12px] text-danger">401 Unauthorized</td>
                  </tr>
                  <tr className="border-b border-stone-border">
                    <td className="px-12 py-8 text-warm-gray">Invalid or inactive API key</td>
                    <td className="px-12 py-8 font-mono text-[12px] text-danger">403 Forbidden</td>
                  </tr>
                  <tr>
                    <td className="px-12 py-8 text-warm-gray">Valid API key</td>
                    <td className="px-12 py-8 font-mono text-[12px] text-success">200 OK</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-8 text-[13px] text-warm-gray">
              Auth is opt-in per route. The current MVP dashboard uses a client-side session for
              demonstration; production deployments enforce Bearer token auth on all{' '}
              <code className="text-[12px]">/api/v1/*</code> routes.
            </p>
          </section>

          <section id="multi-tenancy" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Multi-tenancy</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Each tenant has independent compliance thresholds, retry caps, and LLM budgets. Two
              tenants with different AFA thresholds produce different actions for the same mandate
              amount.
            </p>
            <p className="mt-8 text-[14px] text-warm-gray">
              Razorpay credentials are encrypted at rest using Fernet symmetric encryption (AES-128-CBC
              + HMAC) with a master key. Each tenant's webhook secret is stored both encrypted (for
              HMAC verification) and hashed (for fast lookup).
            </p>
            <p className="mt-8 text-[14px] text-warm-gray">
              Provision a new tenant:
            </p>
            <CodeBlock>{`python scripts/create_tenant.py --name "NBFC Name" --webhook-url https://nbfc.com/callback
python scripts/set_tenant_razorpay.py --tenant-id t_xxx --key-id rzp_test_xxx --key-secret yyy --webhook-secret zzz`}</CodeBlock>
          </section>

          <section id="webhooks" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Webhook events</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Aegis receives and processes the following Razorpay webhook events:
            </p>
            <div className="mt-8 overflow-x-auto rounded-lg border border-stone-border">
              <table className="w-full text-[13px] bg-pure-white">
                <thead>
                  <tr className="border-b border-stone-border">
                    {['Event', 'Aegis Action'].map(h => (
                      <th key={h} scope="col" className="text-left px-12 py-8 font-medium text-warm-gray uppercase text-caption tracking-[0.025em]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['payment.failed', 'Enqueued to ARQ worker for async processing (multi-tenant) or acknowledged (MVP)'],
                    ['payment.captured', 'Updates mandate outcome to "recovered" + writes audit entry'],
                    ['subscription.charged', 'Acknowledged'],
                    ['subscription.pending', 'Acknowledged'],
                    ['subscription.activated', 'Acknowledged'],
                  ].map(([e, a]) => (
                    <tr key={e} className="border-b border-stone-border last:border-b-0">
                      <td className="px-12 py-8 font-mono text-[12px] text-ink-black">{e}</td>
                      <td className="px-12 py-8 text-warm-gray">{a}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="rate-limiting" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Rate limiting</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Tier-2 LLM calls are rate-limited per tenant using a Redis sliding window (60-second
              window). Each tenant has a configurable budget (default: 10 calls/minute).
            </p>
            <ol className="mt-8 list-decimal pl-24 text-[14px] text-warm-gray space-y-4">
              <li>Primary model used while budget is available.</li>
              <li>On exhaustion, downgrades to a smaller fallback model (30 calls/min).</li>
              <li>When both budgets are exhausted, returns <code className="text-[12px]">ESCALATE_TO_HUMAN</code> with rationale <code className="text-[12px]">tier2_budget_exhausted</code>.</li>
            </ol>
            <p className="mt-8 text-[13px] text-warm-gray">
              If Redis is unavailable, the rate limiter gracefully degrades — all Tier-2 calls are
              allowed without limiting (single-tenant MVP mode).
            </p>
          </section>

          <section id="metrics-api" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Metrics (Prometheus)</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Prometheus metrics are exposed at <code className="text-[12px]">/metrics</code> in standard
              Prometheus text format. All counters use <code className="text-[12px]">tenant_id</code> as a label.
            </p>
            <div className="mt-8 overflow-x-auto rounded-lg border border-stone-border">
              <table className="w-full text-[13px] bg-pure-white">
                <thead>
                  <tr className="border-b border-stone-border">
                    {['Metric', 'Type', 'Labels'].map(h => (
                      <th key={h} scope="col" className="text-left px-12 py-8 font-medium text-warm-gray uppercase text-caption tracking-[0.025em]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['aegis_recovery_actions_total', 'Counter', 'tenant_id, action, outcome'],
                    ['aegis_compliance_violations_total', 'Counter', 'tenant_id, violation_rule'],
                    ['aegis_tier2_calls_total', 'Counter', 'tenant_id, model, result'],
                    ['aegis_groq_latency_seconds', 'Histogram', 'tenant_id, model'],
                    ['aegis_active_jobs', 'Gauge', 'tenant_id'],
                  ].map(([m, t, l]) => (
                    <tr key={m} className="border-b border-stone-border last:border-b-0">
                      <td className="px-12 py-8 font-mono text-[12px] text-ink-black">{m}</td>
                      <td className="px-12 py-8 text-warm-gray">{t}</td>
                      <td className="px-12 py-8 font-mono text-[11px] text-warm-gray">{l}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </article>
      </div>
    </MarketingLayout>
  );
}
