import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import AppShell from '../../layouts/AppShell';
import TierSplitChart from '../../components/TierSplitChart';
import RecoveryByCategoryTable from '../../components/RecoveryByCategoryTable';
import HumanReviewQueue from '../../components/HumanReviewQueue';
import { getMetrics } from '../../api/aegis';
import type { AggregateMetrics } from '../../types/aegis';
import { fmtINR } from '../../lib/format';

/**
 * Overview (/app) — answers "how much recovered and what needs a human?".
 * Phase 10: live recovery ticker with 10s auto-refresh.
 */
export default function Dashboard() {
  const [metrics, setMetrics] = useState<AggregateMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getMetrics();
      setMetrics(data);
      setError(null);
    } catch {
      setError('Could not reach the Aegis API. Start it with uvicorn on port 8000.');
    }
  }, []);

  useEffect(() => {
    document.title = 'Overview · Aegis';
    load();
    const interval = setInterval(load, 10_000); // Phase 10: auto-refresh every 10s
    return () => clearInterval(interval);
  }, [load]);

  const empty = metrics && metrics.total_records === 0;

  return (
    <AppShell title="Overview">
      {error && (
        <div role="alert" className="rounded-md bg-danger-tint border border-danger/30 text-danger text-[13px] px-16 py-8">
          {error}
        </div>
      )}

      {!metrics && !error && <p className="text-[14px] text-warm-gray">Loading metrics…</p>}

      {empty && (
        <div className="bg-pure-white rounded-lg border border-stone-border shadow-md p-24 md:p-48 flex flex-col items-center gap-16 text-center">
          <p className="font-roobert text-[20px] md:text-[18px] text-ink-black">No mandates processed yet</p>
          <p className="text-[14px] text-warm-gray max-w-[420px]">
            Upload your first CSV of failed mandates and recovery stats will appear here.
          </p>
          <Link
            to="/app/batch"
            className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white font-medium px-16 py-8 hover:bg-cyan-edge transition-colors"
          >
            Run first batch
          </Link>
        </div>
      )}

      {metrics && metrics.total_records > 0 && (
        <>
          {/* Phase 10: Live Recovery Ticker — prominent */}
          <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-24 md:p-32">
            <p className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
              Live recovery
            </p>
            <p className="mt-8 font-roobert text-[36px] md:text-[48px] leading-none text-success tabular-nums">
              {fmtINR(metrics.rs_recovered || 0)}
            </p>
            <p className="mt-8 text-[13px] text-warm-gray">
              {metrics.recovered_count || 0} payment{metrics.recovered_count === 1 ? '' : 's'} recovered · auto-refreshes every 10s
            </p>
          </section>

          {/* All-time stats */}
          <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24">
            <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
              Recovery summary — all batches
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-16 md:gap-24 mt-16">
              <Stat label="Mandates" value={String(metrics.total_records)} />
              <Stat label="Tier-1 resolved" value={String(metrics.tier1_count)} context={`${metrics.tier1_pct}% deterministic`} />
              <Stat label="Executed" value={String(metrics.executed_count)} context="payment links created" />
              <Stat label="Escalated" value={String(metrics.escalated_count)} context="sent to a human" />
              <Stat
                label="Violations caught"
                value={String(metrics.compliance_violations_caught)}
                context={
                  metrics.compliance_violations_executed === 0
                    ? 'executed: 0 ✓'
                    : `executed: ${metrics.compliance_violations_executed} ⚠`
                }
                tone={metrics.compliance_violations_executed === 0 ? 'success' : 'danger'}
              />
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 md:gap-24">
            <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24">
              <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray mb-16">
                Tier split — deterministic vs LLM
              </h2>
              <TierSplitChart metrics={metrics} />
              <p className="mt-16 text-[12px] text-warm-gray">
                Healthy operation keeps Tier-2 under ~30% of the batch — if it climbs, the rule
                engine needs another rule, not a better prompt.
              </p>
            </section>

            <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24 overflow-x-auto">
              <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray mb-16">
                Recovery by failure category
              </h2>
              <RecoveryByCategoryTable data={metrics.recovery_by_category} />
              <p className="mt-16 text-[12px] text-warm-gray">
                Share of mandates whose recovery action executed successfully, per decline code.
              </p>
            </section>
          </div>

          <HumanReviewQueue />
        </>
      )}
    </AppShell>
  );
}

function Stat({
  label,
  value,
  context,
  tone = 'default',
}: {
  label: string;
  value: string;
  context?: string;
  tone?: 'default' | 'success' | 'danger';
}) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
        {label}
      </p>
      <p className="font-roobert text-[24px] md:text-[28px] leading-none text-ink-black tabular-nums">{value}</p>
      {context && (
        <p
          className={`text-[12px] ${
            tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : 'text-warm-gray'
          }`}
        >
          {context}
        </p>
      )}
    </div>
  );
}
