import type { RecoveryDecision } from '../types/aegis';
import { humanizeAction, shortId } from '../lib/format';

interface Props {
  decision: RecoveryDecision;
  onViewDetail?: (decision: RecoveryDecision) => void;
}

/**
 * THE demo-critical component (design.md §5.4): warning-tinted card with
 * struck-through proposal, cited rule, and redirected final action. Rendered
 * ABOVE the mandate list so overrides are unmissable.
 */
export default function ComplianceOverrideCard({ decision, onViewDetail }: Props) {
  const cr = decision.compliance_result;
  if (!cr.violation_blocked) return null;

  return (
    <article className="rounded-lg border border-warning/40 border-l-4 border-l-warning bg-warning-tint p-16">
      <div className="flex items-center justify-between gap-16 flex-wrap">
        <p className="text-[13px] font-medium text-warning flex items-center gap-8">
          <span aria-hidden="true">⚠</span> Compliance override
        </p>
        {onViewDetail && (
          <button
            onClick={() => onViewDetail(decision)}
            className="rounded-full border border-warning/40 bg-transparent text-warning text-[12px] px-12 py-4 hover:bg-pure-white transition-colors"
          >
            Open full trail
          </button>
        )}
      </div>

      <dl className="mt-12 grid grid-cols-1 sm:grid-cols-2 gap-x-24 gap-y-12 text-[13px]">
        <div>
          <dt className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
            Mandate
          </dt>
          <dd className="mt-2 font-mono text-ink-black">{shortId(decision.mandate_id)}</dd>
        </div>
        <div>
          <dt className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
            Rule enforced
          </dt>
          <dd className="mt-2 font-mono text-danger">{cr.violation_rule}</dd>
        </div>
        <div>
          <dt className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
            Proposed by LLM / rules
          </dt>
          <dd className="mt-2">
            <span className="line-through decoration-danger/60 text-warm-gray">
              {humanizeAction(decision.proposed_action)}
            </span>{' '}
            <code className="text-[11px] text-ash-gray no-underline">
              {decision.proposed_action}
            </code>
          </dd>
        </div>
        <div>
          <dt className="text-caption uppercase tracking-[0.025em] text-warm-gray font-medium">
            Final action
          </dt>
          <dd className="mt-2 text-success">
            {humanizeAction(cr.final_action)}{' '}
            <code className="text-[11px] text-success/70">{cr.final_action}</code>
          </dd>
        </div>
      </dl>

      <p className="mt-12 text-[12px] text-warm-gray">
        No further auto-actions will be taken on this mandate. A human reviews the case before
        anything executes.
      </p>
    </article>
  );
}
