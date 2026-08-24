import { PieChart, Pie, Cell, Tooltip } from 'recharts';

interface Props {
  metrics: { tier1_count: number; tier2_count: number } | null;
}

const COLORS = ['#1c1917', '#c1e1f7']; // soot + sky-wash — monochrome chart palette (design.md §5.4)

/** Tier-1 vs Tier-2 donut; printed counts sit beside it (accessibility rule §6). */
export default function TierSplitChart({ metrics }: Props) {
  if (!metrics) return null;

  const data = [
    { name: 'Tier-1 (deterministic rules)', value: metrics.tier1_count },
    { name: 'Tier-2 (Groq LLM)', value: metrics.tier2_count },
  ];

  return (
    <div className="flex items-center gap-16 flex-wrap">
      <PieChart width={240} height={200}>
        <Pie
          data={data}
          cx={110}
          cy={95}
          innerRadius={48}
          outerRadius={78}
          dataKey="value"
          stroke="#ffffff"
          label={({ value }) => String(value)}
        >
          {data.map((entry, i) => (
            <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
      <ul className="flex flex-col gap-8 text-[13px]">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center gap-8">
            <span
              className="inline-block w-12 h-12 rounded-full border border-stone-border"
              style={{ backgroundColor: COLORS[i] }}
            />
            <span className="text-warm-gray">{d.name}</span>
            <span className="font-medium text-ink-black tabular-nums">{d.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
