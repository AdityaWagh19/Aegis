import { useCallback, useEffect, useState } from 'react';
import { getHumanReview, resolveHumanReview } from '../api/aegis';
import type { HumanReviewItem } from '../types/aegis';
import { fmtDateTime, shortId } from '../lib/format';

/**
 * Escalated mandates awaiting a human (design.md §5.4 Overview page row 3).
 * Resolve posts to the API and removes the item locally.
 */
export default function HumanReviewQueue() {
  const [items, setItems] = useState<HumanReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolving, setResolving] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    try {
      setError(null);
      const data = await getHumanReview();
      setItems(data.items);
    } catch {
      setError('Could not load the review queue. Please try again shortly.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const handleResolve = async (reviewId: string) => {
    setResolving(reviewId);
    try {
      await resolveHumanReview(reviewId);
      setItems(prev => prev.filter(item => item.review_id !== reviewId));
    } catch {
      setError('Failed to resolve that item — try again.');
    } finally {
      setResolving(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-pure-white rounded-lg border border-stone-border shadow-md p-24 text-[14px] text-warm-gray">
        Loading review queue…
      </div>
    );
  }

  return (
    <div className="bg-pure-white rounded-lg border border-stone-border shadow-md overflow-hidden">
      <div className="px-24 py-16 border-b border-stone-border flex items-center justify-between">
        <h3 className="font-roobert text-[18px] text-ink-black">
          Human review queue{' '}
          {items.length > 0 && (
            <span className="text-warm-gray font-inter text-[14px]">({items.length})</span>
          )}
        </h3>
        <button
          onClick={loadQueue}
          className="rounded-full border border-stone-border px-12 py-4 text-[12px] text-warm-gray hover:text-ink-black hover:border-stone-muted transition-colors"
        >
          Refresh
        </button>
      </div>

      {error && (
        <p className="mx-24 mt-16 rounded-md bg-danger-tint text-danger text-[13px] px-12 py-8">
          {error}
        </p>
      )}

      {items.length === 0 ? (
        <div className="px-24 py-32 flex flex-col items-center gap-8">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 2.5 4.5 5.5v6c0 5 3.2 8.4 7.5 10 4.3-1.6 7.5-5 7.5-10v-6L12 2.5Z"
              stroke="#a8a29e"
              strokeWidth="1"
            />
            <path d="m9 12 2 2 4-4" stroke="#15803d" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <p className="text-[14px] text-warm-gray">
            Nothing needs a human right now — every mandate found its path.
          </p>
        </div>
      ) : (
        <table className="w-full text-[13px]">
          <caption className="sr-only">Escalated mandates requiring human review</caption>
          <thead>
            <tr>
              {['Mandate', 'Reason', 'Compliance rule', 'Raised', ''].map(h => (
                <th
                  key={h}
                  scope="col"
                  className={`text-left px-24 py-8 text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray border-b border-stone-border ${
                    h === '' ? 'sr-only' : ''
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.review_id} className="border-b border-stone-border last:border-b-0">
                <td className="px-24 py-8 font-mono text-ink-black">{shortId(item.mandate_id)}</td>
                <td className="px-24 py-8 text-ink-black">{item.reason}</td>
                <td className="px-24 py-8 font-mono text-[12px] text-warning">
                  {item.compliance_rule ?? '—'}
                </td>
                <td className="px-24 py-8 text-warm-gray">{fmtDateTime(item.created_at)}</td>
                <td className="px-24 py-8 text-right">
                  <button
                    onClick={() => handleResolve(item.review_id)}
                    disabled={resolving === item.review_id}
                    className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white text-[12px] font-medium px-12 py-4 hover:bg-cyan-edge disabled:opacity-60 transition-colors"
                  >
                    {resolving === item.review_id ? 'Resolving…' : 'Mark resolved'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
