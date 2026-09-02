import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import MarketingLayout from '../layouts/MarketingLayout';

const CATEGORIES = [
  {
    code: 'INSUFFICIENT_FUNDS',
    cause: 'Debit attempted before salary credit',
    action: 'Schedule post-salary retry',
  },
  {
    code: 'AFA_REQUIRED',
    cause: 'Silent debit above the Rs. 15,000 NPCI threshold',
    action: 'Send UPI intent for approval',
  },
  {
    code: 'MANDATE_PAUSED',
    cause: 'Customer paused via RBI 24h pre-debit notice',
    action: 'Send Hinglish nudge',
  },
  {
    code: 'BANK_TECHNICAL_DECLINE',
    cause: 'Bank timeout or downtime',
    action: 'Retry after backoff',
  },
  {
    code: 'NON_REVOCABLE_HARD_DECLINE',
    cause: 'Loan EMI, second hard decline',
    action: 'Escalate to a human — always',
  },
  {
    code: 'MANDATE_EXPIRED',
    cause: 'e-Mandate validity window lapsed',
    action: 'Send new registration link',
  },
];

/** Mini dashboard mock used inside the floating preview card. */
function PreviewPane({ tab }: { tab: number }) {
  if (tab === 1) {
    return (
      <div className="flex flex-col gap-8 text-left">
        {[
          ['MAND-042', 'NON_REVOCABLE', 'Retry → Escalated'],
          ['MAND-107', 'AFA_REQUIRED', 'Intent push'],
          ['MAND-118', 'INSUF_FUNDS', 'Post-salary'],
        ].map(([id, code, res]) => (
          <div
            key={id}
            className="flex items-center justify-between rounded-md border border-stone-border px-12 py-8 text-[11px]"
          >
            <span className="font-mono">{id}</span>
            <span className="text-warm-gray">{code}</span>
            <span className="font-medium">{res}</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-8 text-left">
      <div className="grid grid-cols-3 gap-8">
        {[
          ['Recovered', 'Rs. 84,500'],
          ['At risk', 'Rs. 3,10,200'],
          ['Violations', '4 caught · 0 executed'],
        ].map(([l, v]) => (
          <div key={l} className="rounded-md border border-stone-border p-8">
            <p className="text-[9px] uppercase tracking-[0.025em] text-warm-gray">{l}</p>
            <p className="text-[12px] font-medium mt-2">{v}</p>
          </div>
        ))}
      </div>
      <div className="rounded-md border border-stone-border h-64 flex items-end gap-8 p-8">
        {[40, 65, 30, 80, 55, 70, 45].map((h, i) => (
          <div key={i} className="flex-1 rounded-sm bg-stone-muted" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}

export default function Landing() {
  const [tab, setTab] = useState(0);

  useEffect(() => {
    document.title = 'Aegis · Compliant mandate recovery';
  }, []);

  return (
    <MarketingLayout>
      {/* Hero */}
      <section className="mx-auto max-w-[1200px] px-16 pt-48 md:pt-96 pb-32 md:pb-64">
        {/* Plain text label — no decorative pill wrapper (audit C1/DS1) */}
        <p className="text-[11px] md:text-[12px] uppercase tracking-[0.025em] text-warm-gray font-medium">
          UPI Autopay × e-NACH recovery
        </p>
        <h1 className="mt-16 md:mt-24 font-roobert font-normal text-[28px] md:text-[42px] lg:text-display leading-[1.15] md:leading-display tracking-[-0.5px] md:tracking-display text-ink-black max-w-[760px]">
          Failed mandates, diagnosed &amp; recovered —{' '}
          <span className="bg-sky-wash rounded-md px-8 text-cyan-edge">compliance-first</span> by
          design.
        </h1>
        <p className="mt-16 md:mt-24 text-[15px] md:text-body-lg leading-body-lg tracking-body-lg text-warm-gray max-w-[620px]">
          Diagnoses why each recurring payment failed and takes the one compliant action. Rules
          resolve most cases instantly; an LLM handles the rest.
        </p>
        <div className="mt-24 md:mt-32 flex items-center gap-12 md:gap-16 flex-wrap">
          <Link
            to="/login"
            className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white font-medium px-16 py-8 hover:bg-cyan-edge transition-colors"
          >
            Open console
          </Link>
          <Link
            to="/docs"
            className="rounded-full border border-stone-border bg-transparent text-ink-black px-16 py-8 hover:bg-pure-white transition-colors"
          >
            Docs
          </Link>
          <span className="text-[12px] md:text-[13px] text-warm-gray">
            Razorpay Test Mode — no live money moved.
          </span>
        </div>
      </section>

      {/* Floating preview — the only shadow-xl surface on this page */}
      <section className="mx-auto max-w-[1200px] px-16 -mt-16">
        <div className="rounded-2xl bg-pure-white shadow-xl p-8">
          <div className="rounded-xl border border-stone-border p-16 md:p-24">
            <div className="flex items-center justify-between mb-16">
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Aegis console — live recovery view
              </p>
              <span className="rounded-full bg-success-tint text-success text-[10px] px-8 py-2 font-medium">
                TEST MODE
              </span>
            </div>
            <PreviewPane tab={tab} />
            <div className="mt-16 flex gap-8 justify-center flex-wrap">
              {['Overview', 'Decision trail', 'Overrides'].map((label, i) => (
                <button
                  key={label}
                  onClick={() => setTab(i)}
                  className={`rounded-full px-12 py-6 md:px-16 md:py-8 text-[12px] md:text-[13px] whitespace-nowrap transition-colors ${
                    tab === i
                      ? 'bg-soot text-pure-white'
                      : 'border border-stone-border text-ink-black hover:bg-stone-canvas'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {/* Audit C8: Illustrative view caption */}
            <p className="mt-12 text-center text-[11px] text-ash-gray">
              Illustrative view — upload a batch to see live data.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-[1200px] px-16 pt-48 md:pt-96 scroll-mt-48">
        <h2 className="font-roobert font-normal text-[24px] md:text-heading-sm leading-tight md:leading-heading-sm tracking-heading-sm text-ink-black">
          Three layers.{' '}
          <span className="bg-sky-wash rounded-md px-8 text-cyan-edge">One gate</span> that never
          sleeps.
        </h2>
        <div className="mt-24 md:mt-48 grid md:grid-cols-3 gap-16">
          {[
            {
              t: 'Rules resolve ~70% instantly',
              b: 'A rule engine classifies all six failure categories instantly — salary cycles, retry caps, AFA thresholds. No LLM call, no latency.',
            },
            {
              t: 'An LLM handles only the rest',
              b: 'Ambiguous cases go to an LLM that can only propose from a fixed list of actions — it explains and drafts, never invents.',
            },
            {
              t: 'Compliance cannot be bypassed',
              b: 'Every proposed action passes a compliance check enforcing NPCI and RBI rules. Violations are caught, logged, and never executed.',
            },
          ].map(c => (
            <article key={c.t} className="rounded-2xl border border-stone-border bg-pure-white p-24 shadow-md">
              <h3 className="font-roobert font-normal text-[18px] text-ink-black">{c.t}</h3>
              <p className="mt-12 text-[14px] text-warm-gray">{c.b}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Six failure categories */}
      <section id="categories" className="mx-auto max-w-[1200px] px-16 pt-48 md:pt-96 scroll-mt-48">
        <h2 className="font-roobert font-normal text-[24px] md:text-heading-sm leading-tight md:leading-heading-sm tracking-heading-sm text-ink-black">
          Six failure categories.{' '}
          <span className="bg-sky-wash rounded-md px-8 text-cyan-edge">Fully modeled.</span>
        </h2>
        <p className="mt-16 text-[14px] text-warm-gray max-w-[560px]">
          These six cover the most common failure modes on UPI Autopay and e-NACH. No global
          dunning tool models them.
        </p>
        <div className="mt-24 md:mt-48 grid sm:grid-cols-2 lg:grid-cols-3 gap-16">
          {CATEGORIES.map(c => (
            <article key={c.code} className="rounded-lg border border-stone-border bg-pure-white p-24 shadow-subtle">
              <code className="text-[12px] font-medium text-ink-black">{c.code}</code>
              <p className="mt-8 text-[13px] text-warm-gray">{c.cause}</p>
              <p className="mt-12 text-[13px] text-cyan-edge">→ {c.action}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Compliance promise */}
      <section className="mx-auto max-w-[1200px] px-16 py-48 md:py-96 pb-96 md:pb-160">
        <blockquote className="max-w-[720px]">
          <p className="text-[16px] md:text-body-lg leading-body-lg text-ink-black">
            "The rule engine decides. The LLM explains and drafts.{' '}
            <span className="bg-sky-wash rounded-md px-8 text-cyan-edge">
              Compliance is unconditional.
            </span>
            "
          </p>
          <footer className="mt-16 text-[13px] text-warm-gray">
            Compliance violations reaching execution:{' '}
            <strong className="text-success">zero</strong> — verified by automated tests on every
            deployment.
          </footer>
        </blockquote>
      </section>
    </MarketingLayout>
  );
}
