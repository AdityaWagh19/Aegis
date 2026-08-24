import type { RecoveryDecision } from '../types/aegis';
import { humanizeAction, humanizeOutcome, outcomeTone, shortId } from '../lib/format';

interface Props {
  decisions: RecoveryDecision[];
  onSelect: (decision: RecoveryDecision) => void;
}

const TONE_CLS: Record<string, string> = {
  success: 'bg-success-tint text-success',
  warning: 'bg-warning-tint text-warning',
  danger: 'bg-danger-tint text-danger',
  info: 'bg-info-tint text-info',
};

export function TierBadge({ tier }: { tier: number }) {
  return tier === 1 ? (
    <span className="inline-block rounded-full bg-soot text-pure-white text-[11px] font-medium px-12 py-4">
      Tier-1
    </span>
  ) : (
    <span className="inline-block rounded-full bg-sky-wash text-cyan-edge text-[11px] font-medium px-12 py-4">
      Tier-2
    </span>
  );
}

/**
 * Batch decision table (design.md §5.4 — mono ids, tier badges, outcome badges).
 * Note: `RecoveryDecision` carries no decline_code field; the decline code is
 * available per-mandate in the drawer via the audit entry and in Audit page rows.
 */
export default function MandateList({ decisions, onSelect }: Props) {
  if (decisions.length === 0) {
    return <p className="text-[14px] text-warm-gray">No decisions in this batch.</p>;
  }

  return (
    <div className="overflow-x-auto bg-pure-white rounded-lg border border-stone-border shadow-md">
      <table className="w-full text-[14px] min-w-[720px]">
        <caption className="sr-only">Decisions for the current batch</caption>
        <thead>
          <tr>
            {['Mandate', 'Tier', 'Proposed', 'Final action', 'Outcome', ''].map(h => (
              <th
                key={h}
                scope="col"
                className={`text-left px-12 py-8 text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray border-b border-stone-border ${
                  h === '' ? 'sr-only' : ''
                }`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {decisions.map(d => {
            const tone = outcomeTone(d.outcome);
            const blocked = d.compliance_result.violation_blocked;
            return (
              <tr
                key={d.mandate_id}
                onClick={() => onSelect(d)}
                onKeyDown={e => {
                  if (e.key === 'Enter') onSelect(d);
                }}
                tabIndex={0}
                role="button"
                aria-label={`Open decision detail for mandate ${shortId(d.mandate_id)}`}
                className="border-b border-stone-border last:border-b-0 hover:bg-stone-canvas cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-signal"
              >
                <td className="px-12 py-8 font-mono text-[13px] text-ink-black">
                  {blocked && (
                    <abbr title="Compliance override" className="text-warning mr-4 no-underline">
                      ⚠
                    </abbr>
                  )}
                  {shortId(d.mandate_id)}
                </td>
                <td className="px-12 py-8">
                  <TierBadge tier={d.tier_that_decided} />
                </td>
                <td className="px-12 py-8 text-warm-gray line-through decoration-ash-gray">
                  {humanizeAction(d.proposed_action)}
                </td>
                <td className="px-12 py-8 text-ink-black">{humanizeAction(d.final_action)}</td>
                <td className="px-12 py-8">
                  <span
                    className={`inline-block rounded-full text-[11px] font-medium px-12 py-4 ${TONE_CLS[tone]}`}
                  >
                    {humanizeOutcome(d.outcome)}
                  </span>
                </td>
                <td className="px-12 py-8 text-right text-cyan-edge text-[13px]">View →</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
