import { useCallback, useEffect, useState } from 'react';
import AppShell from '../../layouts/AppShell';
import { getAuditLog } from '../../api/aegis';
import type { AuditEntry } from '../../types/aegis';
import { fmtDateTime, humanizeAction, humanizeOutcome, outcomeTone, shortId } from '../../lib/format';

const TONE_CLS: Record<string, string> = {
  success: 'bg-success-tint text-success',
  warning: 'bg-warning-tint text-warning',
  danger: 'bg-danger-tint text-danger',
  info: 'bg-info-tint text-info',
};

/**
 * Audit trail (/app/audit) — immutable evidence. Server-side pagination;
 * client-side filter on the loaded page.
 */
export default function Audit() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Audit trail · Aegis';
  }, []);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAuditLog(p, pageSize);
      setEntries(data.entries);
      setTotal(data.total);
      setPage(p);
    } catch {
      setError('Could not load the audit log. Please try again shortly.');
    } finally {
      setLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    load(1);
  }, [load]);

  const filtered = entries.filter(
    e =>
      !query.trim() ||
      e.mandate_id.toLowerCase().includes(query.trim().toLowerCase()) ||
      String(e.final_action ?? '').toLowerCase().includes(query.trim().toLowerCase()),
  );

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <AppShell title="Audit trail">
      <div className="flex items-center justify-between gap-16 flex-wrap">
        <p className="text-[13px] text-warm-gray">
          Append-only — entries can never be edited or deleted. Every mandate decision lands here
          exactly once.
        </p>
        <input
          type="search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Filter by mandate id…"
          aria-label="Filter audit entries"
          className="w-64 rounded-[6px] border border-stone-muted bg-pure-white px-12 py-8 text-[13px] text-ink-black placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-cyan-signal"
        />
      </div>

      {error && (
        <div role="alert" className="rounded-md bg-danger-tint border border-danger/30 text-danger text-[13px] px-16 py-8">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-[14px] text-warm-gray">Loading entries…</p>
      ) : (
        <div className="overflow-x-auto bg-pure-white rounded-lg border border-stone-border shadow-md">
          <table className="w-full text-[13px] min-w-[820px]">
            <caption className="sr-only">Append-only audit log</caption>
            <thead>
              <tr>
                {['When', 'Mandate', 'Tier', 'Proposed', 'Final action', 'Outcome', 'Violation rule'].map(h => (
                  <th
                    key={h}
                    scope="col"
                    className="text-left px-16 py-8 text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray border-b border-stone-border whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-16 py-32 text-center text-warm-gray">
                    No matching entries on this page.
                  </td>
                </tr>
              )}
              {filtered.map(e => {
                const tier = e.tier_that_decided as number | undefined;
                const proposed = e.proposed_action as string | undefined;
                const finalAction = e.final_action as string | undefined;
                const outcome = (e.outcome as string | undefined) ?? '';
                const rule = e.violation_rule as string | null | undefined;
                const tone = TONE_CLS[outcomeTone(outcome)];
                return (
                  <tr key={e.entry_id} className="border-b border-stone-border last:border-b-0 hover:bg-stone-canvas">
                    <td className="px-16 py-8 text-warm-gray whitespace-nowrap">{fmtDateTime(e.timestamp)}</td>
                    <td className="px-16 py-8 font-mono text-ink-black">{shortId(e.mandate_id)}</td>
                    <td className="px-16 py-8 tabular-nums text-ink-black">{tier ?? '—'}</td>
                    <td className="px-16 py-8 text-warm-gray line-through decoration-ash-gray whitespace-nowrap">
                      {proposed ? humanizeAction(proposed) : '—'}
                    </td>
                    <td className="px-16 py-8 text-ink-black whitespace-nowrap">
                      {finalAction ? humanizeAction(finalAction) : '—'}
                    </td>
                    <td className="px-16 py-8">
                      <span className={`inline-block rounded-full text-[11px] font-medium px-12 py-4 ${tone}`}>
                        {outcome ? humanizeOutcome(outcome) : '—'}
                      </span>
                    </td>
                    <td className="px-16 py-8 font-mono text-[12px] text-warning max-w-[220px] truncate">
                      {rule ?? '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between gap-16">
        <p className="text-[12px] text-warm-gray tabular-nums">
          Page {page} of {totalPages} · {total} total entries
        </p>
        <div className="flex gap-8">
          <button
            onClick={() => load(page - 1)}
            disabled={page <= 1 || loading}
            className="rounded-full border border-stone-border px-16 py-8 text-[13px] text-ink-black hover:bg-pure-white disabled:opacity-40 transition-colors"
          >
            ← Previous
          </button>
          <button
            onClick={() => load(page + 1)}
            disabled={page >= totalPages || loading}
            className="rounded-full border border-stone-border px-16 py-8 text-[13px] text-ink-black hover:bg-pure-white disabled:opacity-40 transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    </AppShell>
  );
}
