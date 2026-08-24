# Phase 7: Dashboard

> **Status:** [ ] Not started
> **Estimated duration:** Days 10–11
> **Depends on:** Phase 6 (all API endpoints returning correct data)

---

## Objective

Build a React 18 + TypeScript dashboard that consumes the Aegis API and presents recovery metrics, per-mandate decision trails, compliance override cards, Hinglish message previews, and a CSV batch uploader. The compliance override card is the most important component — it must be clearly visible with all relevant fields rendered, and serve as the centrepiece of the demo.

---

## Scope

- React 18 + TypeScript project in `dashboard/`
- Typed API client (`dashboard/src/api/aegis.ts`)
- 9 components as specified below
- 3 pages: `Dashboard`, `Batch`, `Audit`
- `npm run dev` runs locally at `http://localhost:3000`
- `npm run build` produces a production build in `dashboard/dist/`

---

## Design Decisions and Rationale

**D1 — React with TypeScript, not Streamlit.**
TypeScript enforces the API response shapes at compile time. The `ComplianceOverrideCard` component needs precise control over layout and animation — React gives this; Streamlit does not. The build artifact (`dashboard/dist/`) is served statically by Nginx in production, which is simpler than keeping a Python Streamlit process alive.

**D2 — No state management library (Redux, Zustand).**
All state is local component state or simple prop-drilling. The app is small enough that a state manager adds complexity without benefit. The only shared state is the current batch result, which is passed top-down from `Batch.tsx` to child components.

**D3 — Recharts for data visualisation.**
Recharts is a React-native charting library with TypeScript types. It requires no additional configuration and renders server-side-compatible charts. `PieChart` for tier split, `BarChart` for recovery by category.

**D4 — `ComplianceOverrideCard` renders in amber/red and must be unmissable.**
This is a design requirement, not a preference. Any compliance override in the batch must render a visually distinct card. The card shows: mandate ID, proposed action (struck through), violation rule, final action, and a link to the full audit entry.

**D5 — `BatchUploader` shows a progress indicator during processing.**
Because `process_batch()` processes events sequentially, batches with significant Tier-2 routing can take >30s (worst case: 30% Tier-2 on 200 records = ~60s). The uploader renders a spinner/progress bar after upload. The `POST /api/v1/recovery/batch` response is awaited inline.

---

## Project Initialisation

```bash
cd dashboard
# Use Vite (required — aegis.ts uses import.meta.env.VITE_* which is Vite-specific; CRA uses process.env.REACT_APP_*)
npm create vite@latest . -- --template react-ts
npm install
npm install recharts axios react-dropzone
npm run dev
```

---

## File Structure

```
dashboard/
├── src/
│   ├── api/
│   │   └── aegis.ts
│   ├── components/
│   │   ├── MetricCards.tsx
│   │   ├── TierSplitChart.tsx
│   │   ├── RecoveryByCategoryTable.tsx
│   │   ├── MandateList.tsx
│   │   ├── MandateDetailDrawer.tsx
│   │   ├── ComplianceOverrideCard.tsx
│   │   ├── HinglishMessagePreview.tsx
│   │   ├── HumanReviewQueue.tsx
│   │   └── BatchUploader.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Batch.tsx
│   │   └── Audit.tsx
│   ├── types/
│   │   └── aegis.ts          (TypeScript interfaces matching API response shapes)
│   └── App.tsx
├── public/
└── package.json
```

---

## Sequential Implementation Tasks

### Task 7.1 — Define TypeScript types (`src/types/aegis.ts`)

```typescript
// src/types/aegis.ts
export interface ComplianceResult {
  approved: boolean;
  final_action: string;
  violation_blocked: boolean;
  violation_rule: string | null;
}

export interface RecoveryDecision {
  mandate_id: string;
  tier_that_decided: number;
  proposed_action: string;
  compliance_result: ComplianceResult;
  final_action: string;
  outcome: string;
  rationale: string | null;
  confidence: number | null;
  hinglish_message: string | null;
  alternatives_considered: string[] | null;
}

export interface BatchMetrics {
  total_records: number;
  tier1_count: number;
  tier2_count: number;
  tier1_pct: number;
  recovery_rate: number;
  rs_recovered: number;
  rs_at_risk: number;
  compliance_violations_caught: number;
  compliance_violations_executed: number;
}

export interface BatchResult {
  batch_id: string;
  status: string;
  metrics: BatchMetrics;
  decisions: RecoveryDecision[];
}

export interface HumanReviewItem {
  review_id: string;
  mandate_id: string;
  reason: string;
  compliance_rule: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AuditEntry {
  entry_id: number;
  mandate_id: string;
  timestamp: string;
  [key: string]: unknown;
}

export interface AggregateMetrics {
  total_records: number;
  tier1_count: number;
  tier2_count: number;
  tier1_pct: number;
  executed_count: number;
  escalated_count: number;
  compliance_violations_caught: number;
  compliance_violations_executed: number;
  recovery_by_category: Record<string, number>;
}
```

### Task 7.2 — Implement `src/api/aegis.ts`

```typescript
// src/api/aegis.ts
import axios from 'axios';
import type { BatchResult, AggregateMetrics, HumanReviewItem, AuditEntry } from '../types/aegis';

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const api = axios.create({ baseURL: BASE });

export async function uploadBatch(file: File): Promise<BatchResult> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<BatchResult>('/api/v1/recovery/batch', form);
  return data;
}

export async function getBatch(batchId: string): Promise<BatchResult> {
  const { data } = await api.get<BatchResult>(`/api/v1/recovery/batch/${batchId}`);
  return data;
}

export async function getMetrics(): Promise<AggregateMetrics> {
  const { data } = await api.get<AggregateMetrics>('/api/v1/metrics');
  return data;
}

export async function getAuditLog(page = 1, pageSize = 50): Promise<{ total: number; entries: AuditEntry[] }> {
  const { data } = await api.get(`/api/v1/audit?page=${page}&page_size=${pageSize}`);
  return data;
}

export async function getHumanReview(): Promise<{ total: number; items: HumanReviewItem[] }> {
  const { data } = await api.get('/api/v1/human-review');
  return data;
}
```

### Task 7.3 — Implement `MetricCards.tsx`

Four stat cards on the dashboard front page:
- Rs. recovered (large, green)
- Rs. at risk (large, amber)
- Recovery rate (percentage, formatted)
- Compliance violations caught (non-zero is good; executed must always be 0)

```typescript
// src/components/MetricCards.tsx
import type { BatchMetrics } from '../types/aegis';

interface Props { metrics: BatchMetrics | null; }

const fmt = (n: number) => `Rs. ${n.toLocaleString('en-IN')}`;

export default function MetricCards({ metrics }: Props) {
  if (!metrics) return <div>No batch loaded.</div>;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
      <StatCard label="Recovered" value={fmt(metrics.rs_recovered)} colour="#22c55e" />
      <StatCard label="At Risk" value={fmt(metrics.rs_at_risk)} colour="#f59e0b" />
      <StatCard label="Recovery Rate" value={`${(metrics.recovery_rate * 100).toFixed(1)}%`} colour="#3b82f6" />
      <StatCard label="Violations Caught" value={String(metrics.compliance_violations_caught)} colour="#ef4444" />
    </div>
  );
}

function StatCard({ label, value, colour }: { label: string; value: string; colour: string }) {
  return (
    <div style={{ border: `2px solid ${colour}`, borderRadius: 8, padding: 16 }}>
      <div style={{ color: colour, fontSize: 28, fontWeight: 700 }}>{value}</div>
      <div style={{ color: '#6b7280', fontSize: 13 }}>{label}</div>
    </div>
  );
}
```

### Task 7.4 — Implement `TierSplitChart.tsx`

Pie chart showing Tier-1 vs Tier-2 resolution split using Recharts `PieChart`.

```typescript
// src/components/TierSplitChart.tsx
import { PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';
import type { BatchMetrics } from '../types/aegis';

interface Props { metrics: BatchMetrics | null; }

export default function TierSplitChart({ metrics }: Props) {
  if (!metrics) return null;
  const data = [
    { name: 'Tier-1 (Deterministic)', value: metrics.tier1_count },
    { name: 'Tier-2 (Groq LLM)', value: metrics.tier2_count },
  ];
  return (
    <PieChart width={300} height={220}>
      <Pie data={data} cx={140} cy={100} outerRadius={80} dataKey="value" label>
        <Cell fill="#3b82f6" />
        <Cell fill="#8b5cf6" />
      </Pie>
      <Tooltip />
      <Legend />
    </PieChart>
  );
}
```

### Task 7.5 — Implement `RecoveryByCategoryTable.tsx`

Table showing per-decline-code recovery rate from `AggregateMetrics.recovery_by_category`.

```typescript
// src/components/RecoveryByCategoryTable.tsx
interface Props { data: Record<string, number> | null; }

export default function RecoveryByCategoryTable({ data }: Props) {
  if (!data) return null;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ textAlign: 'left', padding: '8px 12px' }}>Decline Code</th>
          <th style={{ textAlign: 'right', padding: '8px 12px' }}>Recovery Rate</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(data).map(([code, rate]) => (
          <tr key={code} style={{ borderTop: '1px solid #e5e7eb' }}>
            <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>{code}</td>
            <td style={{ padding: '8px 12px', textAlign: 'right' }}>
              {(rate * 100).toFixed(1)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### Task 7.6 — Implement `ComplianceOverrideCard.tsx` (critical)

This is the most important component. It must be visually striking (amber/red border, override label) and display all fields needed for the demo narration.

```typescript
// src/components/ComplianceOverrideCard.tsx
import type { RecoveryDecision } from '../types/aegis';

interface Props { decision: RecoveryDecision; }

export default function ComplianceOverrideCard({ decision }: Props) {
  const { compliance_result, proposed_action, final_action, mandate_id } = decision;
  if (!compliance_result.violation_blocked) return null;

  return (
    <div style={{
      border: '2px solid #ef4444',
      borderRadius: 8,
      padding: 16,
      backgroundColor: '#fef2f2',
      marginBottom: 12,
    }}>
      <div style={{ color: '#ef4444', fontWeight: 700, fontSize: 13, marginBottom: 8 }}>
        COMPLIANCE OVERRIDE
      </div>
      <div style={{ fontSize: 13, color: '#374151' }}>
        <div><strong>Mandate:</strong> <code>{mandate_id}</code></div>
        <div>
          <strong>Proposed:</strong>{' '}
          <span style={{ textDecoration: 'line-through', color: '#9ca3af' }}>
            {proposed_action}
          </span>
        </div>
        <div><strong>Rule:</strong> <code>{compliance_result.violation_rule}</code></div>
        <div style={{ color: '#16a34a' }}>
          <strong>Final action:</strong> {final_action}
        </div>
      </div>
    </div>
  );
}
```

### Task 7.7 — Implement `MandateList.tsx` and `MandateDetailDrawer.tsx`

`MandateList` renders a scrollable table of all decisions in the current batch. Clicking a row opens `MandateDetailDrawer` (a slide-in panel) showing the full decision trail including the compliance result and Hinglish message.

Key columns for `MandateList`:
- Mandate ID (truncated to 8 chars)
- Decline Code
- Tier (1 or 2 badge)
- Proposed Action
- Final Action
- Outcome (colour-coded)
- Violation (amber warning icon if `violation_blocked`)

`MandateDetailDrawer` shows all fields from `RecoveryDecision` plus the full Hinglish message.

### Task 7.8 — Implement `HinglishMessagePreview.tsx`

Renders the Hinglish message in a styled card when `decision.hinglish_message` is non-null. Shown inside `MandateDetailDrawer` for Tier-2 decisions.

```typescript
// src/components/HinglishMessagePreview.tsx
interface Props { message: string | null; }

export default function HinglishMessagePreview({ message }: Props) {
  if (!message) return null;
  return (
    <div style={{
      background: '#f0fdf4',
      border: '1px solid #86efac',
      borderRadius: 6,
      padding: 12,
      fontStyle: 'italic',
      color: '#166534',
    }}>
      <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>
        HINGLISH MESSAGE (DRAFT)
      </div>
      {message}
    </div>
  );
}
```

### Task 7.9 — Implement `BatchUploader.tsx`

```typescript
// src/components/BatchUploader.tsx
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadBatch } from '../api/aegis';
import type { BatchResult } from '../types/aegis';

interface Props { onResult: (result: BatchResult) => void; }

export default function BatchUploader({ onResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (files: File[]) => {
    if (!files[0]) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadBatch(files[0]);
      onResult(result);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [onResult]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'text/csv': ['.csv'] }, maxFiles: 1,
  });

  return (
    <div {...getRootProps()} style={{
      border: '2px dashed #3b82f6', borderRadius: 8, padding: 32,
      textAlign: 'center', cursor: 'pointer',
      background: isDragActive ? '#eff6ff' : '#f9fafb',
    }}>
      <input {...getInputProps()} />
      {loading
        ? <div>Processing batch...</div>
        : <div>{isDragActive ? 'Drop CSV here' : 'Drag CSV or click to upload'}</div>
      }
      {error && <div style={{ color: '#ef4444', marginTop: 8 }}>{error}</div>}
    </div>
  );
}
```

### Task 7.10 — Assemble pages

**`Dashboard.tsx`** — Loads `GET /api/v1/metrics` and `GET /api/v1/human-review` on mount. Renders `MetricCards`, `TierSplitChart`, `RecoveryByCategoryTable`, `HumanReviewQueue`.

**`Batch.tsx`** — Renders `BatchUploader`. On result: renders `MetricCards` (batch metrics), `MandateList` (all decisions). Displays `ComplianceOverrideCard` for every decision where `violation_blocked=true`.

**`Audit.tsx`** — Loads `GET /api/v1/audit` with pagination. Renders a table of all audit entries with mandate ID, timestamp, tier, final action, outcome.

**`App.tsx`** — Tabbed navigation between Dashboard, Batch, and Audit pages.

---

## Validation Strategy

1. `npm run dev` starts without error.
2. Upload `data/demo_10.csv` (generated in Phase 6 smoke test) via the `BatchUploader`.
3. Verify `MetricCards` shows non-zero Rs. at risk and Rs. recovered.
4. Verify `TierSplitChart` shows a non-zero Tier-1 slice.
5. Verify `ComplianceOverrideCard` appears for at least one mandate (inject a non-revocable case into `demo_10.csv`).
6. Verify `HinglishMessagePreview` renders for at least one Tier-2 decision.
7. `npm run build` exits with code 0.

---

## Acceptance Criteria

- [ ] `npm run dev` starts at `http://localhost:3000` without error.
- [ ] `BatchUploader` accepts a CSV, shows loading state, and renders `MandateList` on success.
- [ ] `MetricCards` renders all four stats from the batch result.
- [ ] `TierSplitChart` renders a pie chart with two non-zero segments.
- [ ] `ComplianceOverrideCard` is rendered and visually distinct (red border) for any `violation_blocked=true` decision.
- [ ] `HinglishMessagePreview` renders inside `MandateDetailDrawer` for Tier-2 decisions.
- [ ] `HumanReviewQueue` shows items from `GET /api/v1/human-review`.
- [ ] `Audit.tsx` renders paginated audit log entries.
- [ ] `npm run build` produces `dashboard/dist/` with no TypeScript errors.
- [ ] No `console.error` or unhandled promise rejections in the browser console during the upload flow.

---

## Risks and Trade-offs

| Risk | Likelihood | Mitigation |
|---|---|---|
| CORS error from API | Medium | Verify `ALLOWED_ORIGINS` includes `http://localhost:3000` |
| `recharts` not rendering in strict mode | Low | Use recharts v2.x which supports React 18 |
| Batch upload response too slow (> 30s) | Medium | Show loading spinner; increase axios timeout to 60s |
| TypeScript errors on API response shape | Low | `src/types/aegis.ts` mirrors API response exactly; use `unknown` + narrowing for `payload` field |

---

## Deliverables

- Complete `dashboard/` React app
- `npm run build` artifact in `dashboard/dist/`
- Screenshots of each page for `project-context/progress.md` Day 10/11 entry

---

## Documentation Updates

- Check off Phase 7 tasks in `project-context/tasks.md`
- Record dashboard screenshots in `project-context/progress.md`
- Update `plans/overview.md` Phase 7 status: `[x]`
