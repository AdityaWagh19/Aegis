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
 * Overview (/app) — answers "how much did we recover and what needs a human?"
 * Phase 10: live recovery ticker with 10s auto-refresh.
 * Audit: Business Impact section with Rs. at Risk, Recovery Rate, Analyst Hours Saved.
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
      setError('Could not reach the Aegis API. Please try again shortly.');
    }
  }, []);

  useEffect(() => {
    document.title = 'Overview · Aegis';
    load();
    const interval = setInterval(load, 10_000);
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
          {/* Business Impact */}
          <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24">
            <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray mb-16">
              Business impact
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-16 md:gap-24">
              <ImpactStat
                label="Rs. Recovered"
                value={fmtINR(metrics.rs_recovered || 0)}
                context={`${metrics.recovered_count || 0} payment${metrics.recovered_count === 1 ? '' : 's'} captured`}
                tone="success"
              />
              <ImpactStat
                label="Rs. at Risk"
                value={fmtINR(metrics.rs_at_risk || 0)}
                context={`${metrics.total_records} failed mandates`}
              />
              <ImpactStat
                label="Recovery Rate"
                value={
                  metrics.rs_at_risk > 0
                    ? `${((metrics.rs_recovered || 0) / metrics.rs_at_risk * 100).toFixed(1)}%`
                    : '0%'
                }
                context="of amount at risk"
              />
              <ImpactStat
                label="Violations Prevented"
                value={String(metrics.compliance_violations_caught)}
                context={
                  metrics.compliance_violations_executed === 0
                    ? '0 reached execution'
                    : `${metrics.compliance_violations_executed} reached execution`
                }
                tone={metrics.compliance_violations_executed === 0 ? 'success' : 'danger'}
              />
            </div>
          </section>

          {/* Efficiency */}
          <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24">
            <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray mb-16">
              Operational efficiency
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-16 md:gap-24">
              <ImpactStat
                label="Auto-Resolved"
                value={`${metrics.auto_resolution_rate || 0}%`}
                context={`${metrics.auto_resolved_count || 0} of ${metrics.total_records} without human review`}
              />
              <ImpactStat
                label="Analyst Hours Saved"
                value={`${metrics.analyst_hours_saved || 0} hrs`}
                context="15 min saved per auto-resolved mandate"
              />
              <ImpactStat
                label="Escalation Rate"
                value={`${metrics.total_records > 0 ? ((metrics.escalated_count / metrics.total_records) * 100).toFixed(1) : 0}%`}
                context={`${metrics.escalated_count} routed to a human`}
              />
              <ImpactStat
                label="Tier-1 Resolution"
                value={`${metrics.tier1_pct}%`}
                context={`${metrics.tier1_count} resolved by rules alone`}
              />
            </div>
          </section>

          {/* Live Recovery Ticker */}
          <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24">
            <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray mb-8">
              Live recovery
            </h2>
            <p className="font-roobert text-[36px] md:text-[48px] leading-none text-success tabular-nums">
              {fmtINR(metrics.rs_recovered || 0)}
            </p>
            <p className="mt-8 text-[13px] text-warm-gray">
              {metrics.recovered_count > 0
                ? `${metrics.recovered_count} payment${metrics.recovered_count === 1 ? '' : 's'} recovered · auto-refreshes every 10s`
                : 'Awaiting first captured payment · auto-refreshes every 10s'}
            </p>
          </section>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 md:gap-24">
            <section className="bg-pure-white rounded-lg border border-stone-border shadow-md p-16 md:p-24">
              <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray mb-16">
                Tier split — deterministic vs LLM
              </h2>
              <TierSplitChart metrics={metrics} />
              <p className="mt-16 text-[12px] text-warm-gray">
                Healthy operation keeps LLM-routed cases under ~30%. Higher means more rules are
                needed.
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

function ImpactStat({
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
      <p className={`font-roobert text-[24px] sm:text-[28px] leading-none tabular-nums ${
        tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : 'text-ink-black'
      }`}>
        {value}
      </p>
      {context && (
        <p className={`text-[12px] ${
          tone === 'success' ? 'text-success/70' : tone === 'danger' ? 'text-danger/70' : 'text-warm-gray'
        }`}>
          {context}
        </p>
      )}
    </div>
  );
}
