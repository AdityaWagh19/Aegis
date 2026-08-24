# Phase 7: Dashboard & Frontend

> **Status:** [/] Implementation complete (2026-08-24) — production build green; awaiting one manual browser QA pass for purely visual acceptance items
> **Estimated duration:** Days 10–11
> **Depends on:** Phase 6 (all API endpoints returning correct data)
> **Design system:** `project-context/design.md` (consolidated from `/DESIGN.md`, `/tokens.json`, `/variables.css`, `/theme.css`). All styling MUST consume the Tailwind v4 tokens from `theme.css` — hardcoded hex values in the code samples below are superseded by those tokens.

---

## Objective

Build a React 18 + TypeScript frontend that (a) presents the recovery console — metrics, per-mandate decision trails, compliance override cards, Hinglish message previews, CSV batch uploader — and (b) wraps it in a complete product surface: landing page, docs page, and demo onboarding (login/logout). The compliance override card is the most important component — it must be clearly visible with all relevant fields rendered, and serve as the centrepiece of the demo.

---

## Scope

- React 18 + TypeScript project in `dashboard/` styled with Tailwind v4 (`theme.css` `@theme` tokens)
- Typed API client (`dashboard/src/api/aegis.ts`)
- 9 core components as specified below, restyled to the design system
- **5 routes** (+ app shell): Landing `/`, Docs `/docs`, Login `/login`, App Dashboard `/app`, Batch `/app/batch`, Audit `/app/audit`
- Demo auth gate (localStorage session; real API-key auth arrives Phase 9)
- `npm run dev` runs locally at `http://localhost:3000`
- `npm run build` produces a production build in `dashboard/dist/`

---

## Page Count Discipline

Exactly the routes above — no pricing page, no blog, no settings pages, no team management. Every page earns its place: landing explains, docs unblocks integration, login gates the demo, and the three app pages map 1:1 to user jobs (see status → decide → verify). New pages require a plan amendment.

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

**D6 — Design tokens via Tailwind v4 `@theme`; zero hardcoded colors.**
`theme.css` is copied to `dashboard/src/styles/` and imported first; all components style themselves exclusively with token-derived utilities (e.g., `bg-stone-canvas`, `text-warm-gray`, `border-stone-border`, `rounded-full`, `shadow-md`). The four semantic status tokens from `design.md` §2.3 are added as `@theme` extensions (`--status-success/warning/danger/info`) and used only for outcome meaning — never decoration. This replaces every inline-style hex in the original component sketches below.

**D7 — react-router-dom with three layouts; demo auth gate.**
Routes: `/` Landing, `/docs` Docs (public, MarketingLayout); `/login` Login (AuthLayout); `/app/*` Dashboard/Batch/Audit inside `AppShell`. `AppShell` mounts an `AuthGuard` reading a localStorage session (`lib/auth.ts`). This is explicitly a demo gate — the login page and sidebar state this honestly; Phase 9 API-key auth replaces it without route changes.

**D8 — Marketing pages are content-complete but component-light.**
Landing and Docs reuse app components only where genuinely useful (dashboard preview mock). Landing sections: hero + highlight span, floating preview, how-it-works trio, six failure categories grid, compliance promise, inverted footer. Docs: sticky anchor sidebar + prose covering architecture, compliance rules, CSV format dictionary, full API reference with curl examples. Both render meaningful copy from project-context docs — no lorem ipsum anywhere in the build.

---

## Project Initialisation

```bash
cd dashboard
# Use Vite (required — aegis.ts uses import.meta.env.VITE_* which is Vite-specific; CRA uses process.env.REACT_APP_*)
npm create vite@latest . -- --template react-ts
npm install
npm install recharts axios react-dropzone
npm install react-router-dom
npm install tailwindcss @tailwindcss/vite
npm install @fontsource/inter @fontsource-variable/inter-tight
npm run dev
```

Vite config registers `@tailwindcss/vite`. Entry CSS (`src/styles/index.css`) imports in order: fontsource packages, `./theme.css` (copied from repo root, with the four `--status-*` extensions from design.md §2.3 appended), Tailwind's `@import "tailwindcss";`.

---

## File Structure

```
dashboard/
├── src/
│   ├── api/
│   │   └── aegis.ts
│   ├── styles/
│   │   ├── index.css            (font imports + theme.css + tailwind)
│   │   └── theme.css            (copied from /theme.css + status tokens)
│   ├── lib/
│   │   ├── auth.ts              (demo session get/set/clear)
│   │   └── format.ts            (rupee en-IN, dates, humanizeAction)
│   ├── layouts/
│   │   ├── MarketingLayout.tsx  (top nav + footer)
│   │   ├── AuthLayout.tsx       (centered card)
│   │   └── AppShell.tsx         (sidebar + AuthGuard)
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
│   │   ├── Landing.tsx
│   │   ├── Docs.tsx
│   │   ├── Login.tsx
│   │   └── app/
│   │       ├── Dashboard.tsx    (/app overview)
│   │       ├── Batch.tsx        (/app/batch)
│   │           └── Audit.tsx    (/app/audit)
│   ├── types/
│   │   └── aegis.ts             (TypeScript interfaces matching API response shapes)
│   ├── main.tsx                 (router setup: BrowserRouter + route table)
│   └── App.tsx                  (layout-aware <Routes/> tree)
├── public/
└── package.json
```

> **Restyling rule:** the TypeScript sketches below predate the design system and contain hardcoded colors (e.g. `#22c55e`, `#ef4444`, `#3b82f6`). Implement each component against the token utilities from `project-context/design.md` instead — structure and props remain exactly as specified; only styling sources change. Metric stat values use ink-black text with semantic-color context lines (no colored card borders); ComplianceOverrideCard uses `status-warning` tint/border treatment per design.md §5.4; chart slices use `soot` + `sky-wash`; HinglishMessagePreview keeps its tinted-card pattern via `status-success` tokens.

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

export async function resolveHumanReview(reviewId: string): Promise<{ status: string; review_id: string; resolved_at: string }> {
  const { data } = await api.post(`/api/v1/human-review/${reviewId}/resolve`);
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

### Task 7.8b — Implement `HumanReviewQueue.tsx`

Renders the escalated human review queue with an inline "Mark as Resolved" button for each item.

```typescript
// src/components/HumanReviewQueue.tsx
import { useState, useEffect } from 'react';
import { getHumanReview, resolveHumanReview } from '../api/aegis';
import type { HumanReviewItem } from '../types/aegis';

export default function HumanReviewQueue() {
  const [items, setItems] = useState<HumanReviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadQueue = async () => {
    try {
      const data = await getHumanReview();
      setItems(data.items);
    } catch (e) {
      console.error('Failed to load human review queue', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleResolve = async (reviewId: string) => {
    try {
      await resolveHumanReview(reviewId);
      setItems(prev => prev.filter(item => item.review_id !== reviewId));
    } catch (e) {
      console.error('Failed to resolve item', e);
    }
  };

  if (loading) return <div>Loading review queue...</div>;
  if (items.length === 0) return <div style={{ color: '#6b7280', padding: 16 }}>No items in human review queue.</div>;

  return (
    <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16 }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Human Review Queue ({items.length})</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #e5e7eb', textAlign: 'left', color: '#6b7280' }}>
            <th style={{ padding: '8px 4px' }}>Mandate ID</th>
            <th style={{ padding: '8px 4px' }}>Reason</th>
            <th style={{ padding: '8px 4px' }}>Compliance Rule</th>
            <th style={{ padding: '8px 4px' }}>Created At</th>
            <th style={{ padding: '8px 4px' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.review_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: '8px 4px' }}><code>{item.mandate_id.slice(0, 12)}...</code></td>
              <td style={{ padding: '8px 4px' }}>{item.reason}</td>
              <td style={{ padding: '8px 4px', color: item.compliance_rule ? '#ef4444' : '#6b7280' }}>
                {item.compliance_rule || 'N/A'}
              </td>
              <td style={{ padding: '8px 4px', color: '#6b7280' }}>{new Date(item.created_at).toLocaleTimeString()}</td>
              <td style={{ padding: '8px 4px' }}>
                <button
                  onClick={() => handleResolve(item.review_id)}
                  style={{
                    background: '#3b82f6', color: '#fff', border: 'none',
                    borderRadius: 4, padding: '4px 8px', fontSize: 12, cursor: 'pointer',
                  }}
                >
                  Mark as Resolved
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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

### Task 7.0 — Design-system setup
Copy `/theme.css` → `src/styles/theme.css`; append the four `--status-*` tokens (design.md §2.3); wire `index.css` (fonts → theme → tailwind); register the Tailwind v4 Vite plugin; copy `lib/auth.ts` + `lib/format.ts` specs from design.md; verify a token utility (`bg-stone-canvas`) renders before building anything else.

### Tasks 7.1–7.9 — Types, API client, and the 9 core components
As specified below. Styling per the Restyling rule above.

### Task 7.10a — Layouts and routing
`main.tsx`: `BrowserRouter` with the 6-route table (design.md §5.2). Build `MarketingLayout`, `AuthLayout`, `AppShell` (+`AuthGuard` via `lib/auth.ts`). Sidebar nav: Overview / Batches / Audit trail, env chip "Test mode", Sign out (clears session → `/login`).

### Task 7.10b — Landing page (`/`)
Sections per design.md §5.4: hero (eyebrow tag, display headline with ONE highlight span on "compliance-first", subhead, cyan+ghost CTA pair, test-mode trust line) · floating dashboard preview with tab-pill switcher · how-it-works feature trio · six failure categories 3×2 grid · compliance promise block ("violations reaching execution: 0 — asserted in tests") · inverted footer. Copy sourced from project-context/context.md — no placeholders.

### Task 7.10c — Docs page (`/docs`)
Sticky anchor sidebar (Overview, Two-tier architecture, Compliance rules, CSV format, API reference, Actions allow-list). Prose + tables drawn from project-context docs; endpoint list with method/path pills and curl examples for all seven endpoints; CSV column dictionary table. Code blocks: soot cards, 13px mono.

### Task 7.10d — Login page (`/login`)
AuthLayout card per design.md: email+password fields, cyan CTA, ghost "Continue as guest", demo-gate helper text mentioning Phase 9 API-key auth. On success: `setSession()` → navigate `?next` or `/app`. Inline status-danger hint for empty/invalid input (still permits guest entry).

### Task 7.10e — App pages assembly

**`/app` Dashboard** — Loads `GET /api/v1/metrics` and `GET /api/v1/human-review`. Renders `MetricCards`, `TierSplitChart` (with printed tier counts beside it), `RecoveryByCategoryTable`, `HumanReviewQueue`.

**`/app/batch` Batch** — Three states: empty (dropzone + sample-CSV link + format summary) / processing (spinner + honest timing note) / results. Results order: batch metric stats → ComplianceOverrideCard section FIRST when any `violation_blocked=true` exists → MandateList → MandateDetailDrawer on row click (full decision trail + HinglishMessagePreview + alternatives + collapsed Razorpay response).

**`/app/audit` Audit** — Paginated audit table with mono mandate-id search filter; append-only caption; pill pagination controls.

**Route guards** — `/app/*` wrapped by AuthGuard; unauthenticated → `/login?next=…`.

---

## Validation Strategy

1. `npm run dev` starts without error.
2. Landing `/` renders all sections with real copy; exactly one cyan CTA in the hero; one highlight span per headline.
3. Docs `/docs` renders with working anchor sidebar and curl examples for every endpoint.
4. `/login` gates `/app`: visiting `/app` unauthenticated redirects to login; signing in (or guest) lands on Overview.
5. Upload `data/demo_10.csv` (regenerate: `head -11 data/synthetic.csv > data/demo_10.csv`) via the `BatchUploader`.
6. Verify `MetricCards` shows non-zero Rs. at risk and Rs. recovered.
7. Verify `TierSplitChart` shows a non-zero Tier-1 slice.
8. Verify `ComplianceOverrideCard` appears for at least one mandate (inject a non-revocable case into `demo_10.csv`).
9. Verify `HinglishMessagePreview` renders for at least one Tier-2 decision.
10. Sign out from the sidebar returns to `/login`; browser console stays clean throughout.
11. `npm run build` exits with code 0.

---

## Acceptance Criteria

- [x] `npm run dev` starts at `http://localhost:3000` without error. (Verified live; all 6 routes return HTTP 200.)
- [x] All six routes render: `/`, `/docs`, `/login`, `/app`, `/app/batch`, `/app/audit` — styled exclusively via design tokens (no hardcoded hex in component code). *(Routes serve + full type-checked build passes; visual styling confirmation in the browser pending manual pass.)*
- [x] `AuthGuard`: unauthenticated `/app/*` access redirects to `/login?next=…`; sign-in and guest paths both work; Sign out clears session. *(Implemented in AppShell via lib/auth.ts; behaviour verified by code review — interactive confirmation pending manual pass.)*
- [x] Landing page contains hero + highlight span, floating preview, how-it-works, six-category grid, compliance promise, footer — with real product copy and zero lorem ipsum.
- [x] Docs page documents all seven API endpoints with curl examples plus the CSV column dictionary.
- [x] `BatchUploader` accepts a CSV, shows loading state, and renders `MandateList` on success. *(Underlying API chain verified live end-to-end: upload 202 → poll 200 with decisions.)*
- [ ] `MetricCards` renders all four stats from the batch result (ink values, semantic context lines). *(Implemented; visual pass pending.)*
- [ ] `TierSplitChart` renders a donut/pie with two non-zero segments using the monochrome chart palette. *(Implemented; visual pass pending.)*
- [ ] `ComplianceOverrideCard` is rendered and visually distinct for any `violation_blocked=true` decision, shown before the mandate list. *(Implemented; the demo_10 batch returns 6 blocked violations so data is present; visual pass pending.)*
- [ ] `HinglishMessagePreview` renders inside `MandateDetailDrawer` for Tier-2 decisions. *(Implemented; visual pass pending.)*
- [x] `HumanReviewQueue` shows items from `GET /api/v1/human-review` with working resolve buttons. *(Endpoint verified live — 5 items returned; resolve wired to POST.)*
- [ ] Audit page renders paginated entries with search filter. *(Implemented against verified paginated endpoint; visual pass pending.)*
- [x] `npm run build` produces `dashboard/dist/` with no TypeScript errors.
- [ ] No `console.error` or unhandled promise rejections in the browser console during landing → login → upload → audit flow. *(Requires an interactive browser session — final QA step.)

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
