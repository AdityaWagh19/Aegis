import type { RecoveryDecision } from '../types/aegis';
import { humanizeAction, fmtPct, shortId } from '../lib/format';
import HinglishMessagePreview from './HinglishMessagePreview';

interface Props {
  decision: RecoveryDecision | null;
  onClose: () => void;
}

/**
 * Right slide-in panel (design.md §3.4 drawer spec): 420px, white surface,
 * hairline left border, shadow-xl. Esc + overlay click to close.
 */
export default function MandateDetailDrawer({ decision, onClose }: Props) {
  const open = decision !== null;

  if (!open || !decision) return null;

  const d = decision;
  const cr = d.compliance_result;

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label={`Decision detail for mandate ${shortId(d.mandate_id)}`}
    >
      <button
        aria-label="Close details"
        onClick={onClose}
        className="absolute inset-0 bg-soot/20 cursor-default"
        autoFocus
      />
      <aside className="absolute right-0 top-0 h-full w-full max-w-[440px] bg-pure-white border-l border-stone-border shadow-xl overflow-y-auto">
        <div className="sticky top-0 bg-pure-white border-b border-stone-border px-24 py-16 flex items-center justify-between z-10">
          <h2 className="font-roobert text-[18px] text-ink-black">Decision trail</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-full w-32 h-32 flex items-center justify-center text-warm-gray hover:text-ink-black hover:bg-stone-canvas transition-colors text-[18px]"
          >
            ✕
          </button>
        </div>

        <div className="px-24 py-24 flex flex-col gap-24">
          {/* Identity */}
          <section className="flex flex-col gap-8">
            <p className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
              Mandate ID
            </p>
            <code className="text-[13px] text-ink-black break-all">{d.mandate_id}</code>
          </section>

          {/* Tier + outcome */}
          <section className="grid grid-cols-2 gap-16">
            <div className="flex flex-col gap-4">
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Decided by
              </p>
              <p className="text-[14px] text-ink-black">
                Tier-{d.tier_that_decided} {d.tier_that_decided === 1 ? '(rules)' : '(Groq LLM)'}
              </p>
            </div>
            <div className="flex flex-col gap-4">
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Outcome
              </p>
              <p className="text-[14px] text-ink-black">{d.outcome}</p>
            </div>
            {d.confidence !== null && (
              <div className="flex flex-col gap-4 col-span-2">
                <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                  Confidence
                </p>
                <div className="flex items-center gap-12">
                  <div className="flex-1 h-8 rounded-full bg-stone-canvas border border-stone-border overflow-hidden">
                    <div
                      className="h-full bg-cyan-signal rounded-full"
                      style={{ width: `${Math.round((d.confidence ?? 0) * 100)}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-[13px] text-warm-gray">
                    {fmtPct(d.confidence, 0)}
                  </span>
                </div>
              </div>
            )}
          </section>

          {/* Action flow */}
          <section className="rounded-lg border border-stone-border p-16 flex flex-col gap-12">
            <div>
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Proposed action
              </p>
              <p className={`mt-4 ${cr.violation_blocked ? 'line-through decoration-ash-gray text-warm-gray' : 'text-ink-black'}`}>
                {humanizeAction(d.proposed_action)}{' '}
                <code className="text-[11px] text-ash-gray">{d.proposed_action}</code>
              </p>
            </div>

            <div className="border-t border-stone-border pt-12">
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Compliance gate
              </p>
              {cr.violation_blocked ? (
                <>
                  <p className="mt-4 text-warning text-[14px]">
                    ⚠ Blocked — {cr.violation_rule}
                  </p>
                  <p className="text-[12px] text-warm-gray mt-4">
                    The proposed action violated a compliance rule and was redirected before
                    execution.
                  </p>
                </>
              ) : (
                <p className="mt-4 text-success text-[14px]">✓ Approved — no violation detected</p>
              )}
            </div>

            <div className="border-t border-stone-border pt-12">
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Final action (executed path)
              </p>
              <p className="mt-4 text-ink-black">
                {humanizeAction(d.final_action)}{' '}
                <code className="text-[11px] text-ash-gray">{d.final_action}</code>
              </p>
            </div>
          </section>

          {/* Rationale */}
          {d.rationale && (
            <section>
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Rationale
              </p>
              <p className="mt-4 text-[14px] text-ink-black">{d.rationale}</p>
            </section>
          )}

          {/* Alternatives */}
          {d.alternatives_considered && d.alternatives_considered.length > 0 && (
            <section>
              <p className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
                Alternatives considered
              </p>
              <ul className="mt-8 flex flex-wrap gap-8">
                {d.alternatives_considered.map(a => (
                  <li
                    key={a}
                    className="rounded-full border border-stone-border px-12 py-4 text-[12px] text-warm-gray"
                  >
                    {humanizeAction(a)}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Hinglish draft */}
          <HinglishMessagePreview message={d.hinglish_message} />

          {/* Razorpay response */}
          {d.razorpay_response && (
            <details className="group">
              <summary className="cursor-pointer text-[13px] text-cyan-edge select-none">
                Razorpay response
              </summary>
              <pre className="mt-8 bg-soot text-pure-white rounded-lg p-16 text-[12px] overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(d.razorpay_response, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </aside>
    </div>
  );
}
