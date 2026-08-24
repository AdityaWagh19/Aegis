interface Props {
  data: Record<string, number> | null;
}

/** Per-decline-code recovery rate table (flat card, hairline rows). */
export default function RecoveryByCategoryTable({ data }: Props) {
  if (!data) return null;

  const entries = Object.entries(data);
  if (entries.length === 0) {
    return <p className="text-[13px] text-warm-gray">No category data yet.</p>;
  }

  return (
    <table className="w-full text-[14px]">
      <caption className="sr-only">Recovery rate by decline code</caption>
      <thead>
        <tr>
          <th
            scope="col"
            className="text-left px-12 py-8 text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray"
          >
            Decline code
          </th>
          <th
            scope="col"
            className="text-right px-12 py-8 text-caption leading-caption font-medium uppercase tracking-[0.025em] text-warm-gray"
          >
            Recovery rate
          </th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([code, rate]) => (
          <tr key={code} className="border-t border-stone-border hover:bg-stone-canvas">
            <td className="px-12 py-8 font-mono text-[13px] text-ink-black">{code}</td>
            <td className="px-12 py-8 text-right tabular-nums text-ink-black">
              {(rate * 100).toFixed(1)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
