import type { BatchMetrics } from '../types/aegis';
import { fmtINR, fmtPct } from '../lib/format';

interface Props {
  metrics: BatchMetrics | null;
  title?: string;
}

/**
 * Four metric stats (design.md §3.4): flat cards, caption label + Roobert-token
 * value in ink-black; semantic color appears only in the context line.
 */
export default function MetricCards({ metrics, title }: Props) {
  if (!metrics) {
    return (
      <p className="text-[14px] text-warm-gray">No batch loaded — upload a CSV to see results.</p>
    );
  }

  const stats = [
    {
      label: 'Recovered',
      value: fmtINR(metrics.rs_recovered),
      context: `${fmtPct(metrics.recovery_rate)} of amount at risk`,
      tone: 'text-success' as const,
    },
    {
      label: 'At risk',
      value: fmtINR(metrics.rs_at_risk),
      context: `${metrics.total_records} mandates in batch`,
      tone: 'text-warning' as const,
    },
    {
      label: 'Recovery rate',
      value: fmtPct(metrics.recovery_rate),
      context: `Tier-1 resolved ${metrics.tier1_pct}% without LLM`,
      tone: 'text-warm-gray' as const,
    },
    {
      label: 'Violations caught',
      value: String(metrics.compliance_violations_caught),
      context:
        metrics.compliance_violations_executed === 0
          ? 'executed: 0 ✓'
          : `executed: ${metrics.compliance_violations_executed} ⚠`,
      tone:
        metrics.compliance_violations_executed === 0
          ? ('text-success' as const)
          : ('text-danger' as const),
    },
  ];

  return (
    <section className="flex flex-col gap-12">
      {title && (
        <h2 className="font-roobert text-[18px] text-ink-black" style={{ letterSpacing: '-0.017em' }}>
          {title}
        </h2>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-16">
        {stats.map(s => (
          <div
            key={s.label}
            className="bg-pure-white rounded-lg border border-stone-border shadow-md p-24"
          >
            <p className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
              {s.label}
            </p>
            <p className="mt-8 font-roobert text-[28px] leading-none text-ink-black">{s.value}</p>
            <p className={`mt-8 text-[12px] ${s.tone}`}>{s.context}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
