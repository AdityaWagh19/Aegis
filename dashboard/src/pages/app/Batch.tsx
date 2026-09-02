import { useState, useEffect } from 'react';
import AppShell from '../../layouts/AppShell';
import BatchUploader from '../../components/BatchUploader';
import MetricCards from '../../components/MetricCards';
import MandateList from '../../components/MandateList';
import MandateDetailDrawer from '../../components/MandateDetailDrawer';
import ComplianceOverrideCard from '../../components/ComplianceOverrideCard';
import { getBatch } from '../../api/aegis';
import type { BatchResult, BatchUploadResponse, RecoveryDecision } from '../../types/aegis';

/**
 * Batches (/app/batch) — upload a CSV, watch decisions land, inspect any
 * mandate. Compliance overrides render ABOVE the list so they are unmissable.
 */
export default function Batch() {
  const [result, setResult] = useState<BatchResult | null>(null);
  const [uploadMeta, setUploadMeta] = useState<BatchUploadResponse | null>(null);
  const [selected, setSelected] = useState<RecoveryDecision | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Batches · Aegis';
  }, []);

  const handleResult = (meta: BatchUploadResponse) => {
    setUploadMeta(meta);
    // The POST returns metrics; the full decisions live behind the batch id cache.
    getBatch(meta.batch_id)
      .then(full => setResult(full))
      .catch(() =>
        setPollError('Batch completed but its detail could not be reloaded — metrics above are final.'),
      );
  };

  const overrides = result?.decisions.filter(d => d.compliance_result.violation_blocked) ?? [];

  return (
    <AppShell title="Batches">
      {!result && !uploadMeta && (
        <section className="flex flex-col gap-16">
          <p className="text-[14px] text-warm-gray max-w-[620px]">
            Upload a CSV of failed mandates. Aegis classifies each one, proposes the compliant
            action, and records the decision — you review anything that was escalated or blocked.
          </p>
          <BatchUploader onResult={handleResult} />
          <div className="bg-pure-white rounded-lg border border-stone-border shadow-subtle p-24 text-[13px] text-warm-gray">
            <p className="font-medium text-ink-black mb-8">What happens after upload</p>
            <ol className="list-decimal pl-24 space-y-4">
              <li>Rules classify most mandates instantly.</li>
              <li>Ambiguous cases go to the LLM — this is the slow part.</li>
              <li>Every proposal passes the compliance gate; violations are redirected and flagged.</li>
              <li>Approved actions execute against Razorpay test mode; every decision is audited.</li>
            </ol>
          </div>
        </section>
      )}

      {uploadMeta && !result && (
        <>
          <MetricCards metrics={uploadMeta.metrics} title="Batch complete" />
          {pollError && <p className="text-[13px] text-warning">{pollError}</p>}
          <p className="text-[13px] text-warm-gray">Loading decision trail…</p>
        </>
      )}

      {uploadMeta && result && (
        <>
          <MetricCards metrics={uploadMeta.metrics} title={`Batch ${uploadMeta.batch_id.slice(0, 8)}… — complete`} />

          {uploadMeta.parse_errors.length > 0 && (
            <details className="rounded-lg bg-info-tint border border-info/30 p-16 text-[13px] text-info">
              <summary className="cursor-pointer font-medium">
                {uploadMeta.parse_errors.length} row(s) could not be parsed and were skipped
              </summary>
              <ul className="mt-8 list-disc pl-24 space-y-2">
                {uploadMeta.parse_errors.map((e, i) => (
                  <li key={i} className="font-mono text-[12px]">
                    {e}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {overrides.length > 0 ? (
            <section className="flex flex-col gap-12">
              <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
                Compliance overrides ({overrides.length}) — blocked before execution
              </h2>
              {overrides.map(d => (
                <ComplianceOverrideCard key={d.mandate_id} decision={d} onViewDetail={setSelected} />
              ))}
            </section>
          ) : (
            <p className="text-[13px] text-success bg-success-tint rounded-md px-16 py-8 w-fit">
              ✓ No compliance violations in this batch.
            </p>
          )}

          <section className="flex flex-col gap-12">
            <h2 className="text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray">
              Decisions ({result.decisions.length})
            </h2>
            <MandateList decisions={result.decisions} onSelect={setSelected} />
            <button
              onClick={() => {
                setResult(null);
                setUploadMeta(null);
                setPollError(null);
              }}
              className="self-start rounded-full border border-stone-border px-16 py-8 text-[14px] text-ink-black hover:bg-pure-white transition-colors"
            >
              Run another batch
            </button>
          </section>

          <MandateDetailDrawer decision={selected} onClose={() => setSelected(null)} />
        </>
      )}
    </AppShell>
  );
}


