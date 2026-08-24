import MarketingLayout from '../layouts/MarketingLayout';

const NAV = [
  ['overview', 'Overview'],
  ['architecture', 'Two-tier architecture'],
  ['compliance', 'Compliance rules'],
  ['csv-format', 'CSV upload format'],
  ['api', 'API reference'],
  ['actions', 'Action allow-list'],
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

export default function Docs() {
  if (typeof document !== 'undefined') document.title = 'Docs · Aegis';

  return (
    <MarketingLayout>
      <div className="mx-auto max-w-[1200px] px-16 py-64 grid lg:grid-cols-[200px_1fr] gap-48">
        {/* Anchor sidebar */}
        <aside className="hidden lg:block">
          <nav className="sticky top-64 flex flex-col gap-4 border-l border-stone-border">
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

        <article className="prose-aegis max-w-[720px] flex flex-col gap-32">
          <header>
            <h1 className="font-roobert font-normal text-heading-sm leading-heading-sm tracking-heading-sm text-ink-black">
              Aegis documentation
            </h1>
            <p className="mt-12 text-body-lg leading-body-lg text-warm-gray">
              Everything needed to run batches against the API and understand every action it can
              take. Base URL: <code className="text-ink-black">http://localhost:8000</code>.
            </p>
          </header>

          <section id="overview" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Overview</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Aegis ingests failed UPI Autopay / e-NACH mandate events, diagnoses the root cause, and
              executes the one compliant recovery action per mandate — with an append-only audit
              trail for every decision.
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
              <Curl>{`curl -X POST http://localhost:8000/api/v1/recovery/batch \\\n  -F "file=@mandates.csv"`}</Curl>
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/recovery/batch/{batch_id}">
              Full decisions for a processed batch (available for the lifetime of the server process).
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/metrics">
              All-time aggregates: tier split, executed/escalated counts, violations caught vs
              executed, recovery rate by category.
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/audit?page=1&page_size=50">
              Paginated append-only audit trail.
              <Curl>{`curl "http://localhost:8000/api/v1/audit?page=1&page_size=10"`}</Curl>
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/mandates/{mandate_id}">
              First audit entry for a single mandate — the full decision record.
            </Endpoint>

            <Endpoint method="GET" path="/api/v1/human-review">
              Unresolved escalated mandates. Resolve one:
              <Curl>{`curl -X POST http://localhost:8000/api/v1/human-review/{review_id}/resolve`}</Curl>
            </Endpoint>

            <Endpoint method="POST" path="/webhooks/razorpay">
              Subscription lifecycle webhooks. Requests must carry{' '}
              <code className="text-[12px]">X-Razorpay-Signature</code> — HMAC-SHA256 of the raw body
              using RAZORPAY_WEBHOOK_SECRET. Unsigned requests get <strong>403</strong>.
            </Endpoint>
          </section>

          <section id="actions" className="scroll-mt-48">
            <h2 className="font-roobert font-normal text-subheading tracking-subheading text-ink-black">Action allow-list</h2>
            <p className="mt-8 text-[14px] text-warm-gray">
              Tier-2 can propose only these seven actions — Pydantic rejects anything else at parse
              time:
            </p>
            <ul className="mt-8 grid sm:grid-cols-2 gap-8">
              {[
                'RETRY_AFTER_BACKOFF',
                'SCHEDULE_POST_SALARY',
                'SEND_UPI_INTENT_PUSH',
                'SEND_MANDATE_RENEWAL_LINK',
                'SEND_HINGLISH_NUDGE',
                'ESCALATE_TO_HUMAN',
                'NO_ACTION_MONITORING',
              ].map(a => (
                <li key={a} className="rounded-md border border-stone-border bg-pure-white px-12 py-8 font-mono text-[12px] text-ink-black">
                  {a}
                </li>
              ))}
            </ul>
          </section>
        </article>
      </div>
    </MarketingLayout>
  );
}
