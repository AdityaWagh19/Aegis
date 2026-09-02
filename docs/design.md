# Aegis Design System — design.md

> **Status:** Authoritative visual + UX specification for all Aegis frontend work (Phase 7 dashboard, marketing pages, onboarding).
> **Consolidated from:** `/DESIGN.md` (style reference), `/tokens.json` (design tokens), `/variables.css` (CSS custom properties), `/theme.css` (Tailwind v4 `@theme` block). Those four files remain the raw source of truth for token values; this document is the single reference for *how to apply them to Aegis*.
> **Origin:** Seline Analytics style extraction (`seline.so`, July 2026). Theme: light. Feel: "quiet analyst's desk on warm paper."

---

## 1. Design Philosophy — Aegis Adaptation

Aegis is a compliance-grade recovery console for Indian fintech ops teams. The design language is **editorial analytics: calm, near-monochrome, confident** — a warm-stone paper canvas, flat white cards structured by hairline borders, whisper-weight display type, and exactly one chromatic voice (cyan) reserved for actions.

What this means concretely for Aegis:

1. **The data is the hero.** Dashboards read like well-set documents, not cockpit UIs. No gradient chrome, no glassmorphism, no decorative color washes.
2. **Cyan = "switched on."** The single accent (#3ba6f1) marks primary actions and active states only. If everything is blue, nothing is.
3. **Compliance moments earn emphasis through structure, not louder color** — a distinct border treatment, an icon, a struck-through proposal — with one sanctioned semantic status palette (§2.3) used sparingly for outcome meaning.
4. **India-first content.** Rupee formatting (`Rs. 1,23,456` en-IN), Hinglish message previews rendered verbatim as first-class product output, plain-English explanations of NPCI/RBI rules beside every technical field.

---

## 2. Design Tokens

### 2.1 Core Palette

| Name | Value | Token | Role |
|---|---|---|---|
| Stone Canvas | `#fafaf9` | `--color-stone-canvas` | Page background — warm paper, never screen-white |
| Pure White | `#ffffff` | `--color-pure-white` | Card surfaces, elevated panels, input fills |
| Stone Border | `#e8e6e5` | `--color-stone-border` | 1px hairlines — THE primary structural device (cards, nav, tables, inputs) |
| Stone Muted | `#d6d3d1` | `--color-stone-muted` | Secondary borders, input borders, subtle tints |
| Ash Gray | `#a8a29e` | `--color-ash-gray` | Muted helper text, icon strokes, disabled states |
| Warm Gray | `#78716c` | `--color-warm-gray` | Body text, nav links, secondary copy |
| Ink Black | `#0c0a09` | `--color-ink-black` | Headings, emphasized body, strong icons |
| Soot | `#1c1917` | `--color-soot` | Inverted surfaces: active tab pills, dark panels (sparingly) |
| Sky Wash | `#c1e1f7` | `--color-sky-wash` | Soft pill-wash behind highlighted headline phrases |
| Cyan Signal | `#3ba6f1` | `--color-cyan-signal` | Primary CTA fill, active states, focus rings — the only chromatic voice |
| Cyan Edge | `#3398e1` | `--color-cyan-edge` | Highlight-span text color, outlined-action borders, linked labels. Never the CTA fill |

### 2.2 Surfaces & Elevation

| Level | Surface | Value | Used for |
|---|---|---|---|
| 0 | Canvas | `#fafaf9` | Full-page background |
| 1 | Card | `#ffffff` | Content cards, nav bar, inputs, tables |
| 2 | Floating Preview | `#ffffff` + `--shadow-xl` | Exactly ONE element per page: hero dashboard mockup / the primary batch-result panel on demo day |
| 3 | Inverted | `#1c1917` | Active tab pills, dark footer band, inverted callouts (rare) |

Elevation tokens:
- Content card: `--shadow-md` → `rgba(0,0,0,.05) 0 4px 16px 0`
- Floating preview: `--shadow-xl` → `rgba(17,12,46,.12) 0 12px 45px 0`
- Small chips/icons: `--shadow-sm`
- Hairline lift (nav/buttons): `--shadow-subtle`

### 2.3 Semantic Status Tokens — Sanctioned Extension

The core palette forbids new *accent* colors. Outcome/status colors in a payments-recovery product are **meaning-bearing semantics, not decoration**, so a minimal desaturated set is sanctioned. Rules of use: status colors appear ONLY as text, icon strokes, badge text/fill-tints, and left-border accents — never as large filled surfaces, never in headlines, never as button fills (primary action stays cyan).

| Token | Text/Stroke | Tint Fill | Meaning in Aegis |
|---|---|---|---|
| `--status-success` | `#15803d` | `#ecfdf5` | Executed payment link, resolved review, approved compliance |
| `--status-warning` | `#b45309` | `#fffbeb` | Compliance override caught, at-risk amount, pending review |
| `--status-danger` | `#b91c1c` | `#fef2f2` | Failed execution, blocked violation label |
| `--status-info` | `#0369a1` | `#f0f9ff` | Mocked notification, monitoring state, neutral notices |

(All four pass ≥4.5:1 contrast on their tint fills and on white.)

### 2.4 Typography

**Families**

| Token | Family | Use |
|---|---|---|
| `--font-roobert` *(display token)* | Roobert → substitute **Inter Tight** (self-hosted via Fontsource) with system-ui fallback | All display + headings |
| `--font-inter` | Inter (self-hosted via Fontsource) | Body, nav, UI, captions, tables |

> **Font sourcing rule:** Roobert is a commercial typeface — do NOT bundle it. Load Inter Tight under the display token; keep the CSS variable name `--font-roobert` so token names stay stable across source files. Weights: Inter Tight 400/500; Inter 400/500/600. No other weights anywhere.

**Scale**

| Role | Size | Line height | Tracking | Face | Token |
|---|---|---|---|---|---|
| caption | 10px | 2.3 | — | Inter 500 | `--text-caption` |
| body (dominant) | 14px | 1.64 | +0.004em | Inter 400 | *(base UI rhythm)* |
| body-lg | 16px | 1.69 | +0.048px | Inter 400 | `--text-body-lg` |
| subheading | 20px | 1.2 | −0.1px | Roobert 400 | `--text-subheading` |
| heading-sm | 32px | 1.25 | −0.8px | Roobert 400 | `--text-heading-sm` |
| display | 52px | 1.12 | −1.092px | Roobert 400 | `--text-display` |

Additional Inter steps from tokens.json for dense UI: 12px (1.33–1.92 lh), 13px (1.54–1.77 lh), 15px (1.53 lh), 18px (1.5–1.56 lh).

**Usage rules**
- Display/heading weight is always **400** — authority through restraint. Never 600/700 headings; emphasize with size or the highlight span.
- 14px Inter 400 / 1.64 is the dominant body rhythm; do not break it for marketing copy.
- Positive tracking (+0.004em) at small sizes keeps dense tables legible; negative tracking only ≥20px display sizes.

### 2.5 Spacing & Layout

Base unit 4px. Scale: 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96, 160 (`--spacing-*`).
Layout constants: page max-width **1200px** centered · section gap **96px** · card padding **24px** · element gap **8px**.
Density: compact. Marketing sections breathe at 96–160px vertical; app views use tighter 24–48px section rhythm inside the app shell.

### 2.6 Border Radius

| Element | Value | Token |
|---|---|---|
| Buttons, tags, badges, tab pills | 9999px | `--radius-full` |
| Cards | 10px | `--radius-lg` / `--radius-cards` |
| Feature/hero cards | 16px | `--radius-2xl` / `--radius-feature-card` |
| Inputs | 6px | `--radius-inputs` |
| Icons | 4px | `--radius-md` / `--radius-icons` |

### 2.7 Iconography & Imagery

- Icons: **1px-stroke outline style**, ink-black or cyan-signal, never filled, 16/20px sizes.
- Brand glyph: small shield/spark mark (Aegis) rendered like the reference logo: compact black glyph + wordmark, Inter 500 14px.
- Mascot/sticker personality element: allowed once per page section max, outline SVG, grayscale with soft drop shadow — recommended Aegis motif: a small shield character peeking from card edges. Never animate it.
- Photography: none. Product screenshots/dashboard previews ARE the imagery; apply `filter: grayscale(1) contrast(0.94)` for the muted "product photography" treatment on marketing previews only (never on the live dashboard).

---

## 3. Component Specifications

All components consume tokens via Tailwind v4 utility classes generated from `theme.css` (`@theme`). Hardcoded hexes are forbidden in component code.

### 3.1 Buttons

| Variant | Spec |
|---|---|
| Primary CTA | Pill (`--radius-full`), fill `cyan-signal`, 1px border `cyan-edge`, white text, Inter 500, padding 8×16, `--shadow-subtle`. **Max one per viewport.** Hover: `cyan-edge` fill. |
| Ghost | Pill, transparent fill, 1px `stone-border`, ink-black text 400, padding 8×16. Hover: border `stone-muted`, bg `pure-white`. |
| Small action (table rows) | Pill, ghost spec at 12px text, padding 4×10. Primary micro-actions may use `cyan-signal` fill. |
| Destructive/resolving | Ghost shape with `status-danger` text/border tint; confirm state flips to `status-success`. |

### 3.2 Inputs
White fill, 6px radius, 1px `stone-muted` border, placeholder `warm-gray`, padding 4×12, focus ring 2px `cyan-signal`. Labels: 13px Inter 500 ink-black above field. Helper/error text 12px (`ash-gray` / `status-danger`).

### 3.3 Cards
- **Flat content card**: white, radius 10px, 1px `stone-border` (the structure), padding 24, optional `--shadow-md`.
- **Feature card**: radius 16px, same border logic, used on landing feature grid.
- **Floating preview**: radius 16px, 8px internal frame padding, `--shadow-xl`; ONE per page.

### 3.4 Data Display
- **Metric stat**: flat card; label 13px `warm-gray` uppercase tracking +0.025em; value 28–32px Roobert 400 ink-black; delta/context line 12px semantic-status text. No colored card borders by default — status color appears only in the value/context line when meaningful.
- **Badge/tag**: pill, 11–12px Inter 500; tier badge: Tier-1 = `soot` fill/white text, Tier-2 = `sky-wash` fill/`cyan-edge` text; outcome badges use §2.3 tints.
- **Tables**: header row 12px Inter 500 `warm-gray`, uppercase; rows separated by 1px `stone-border`; hover row bg `#fafaf9`; numeric columns right-aligned, `tabular-nums`; monospace only for IDs/codes.
- **Tab pills**: inactive transparent + 1px `stone-border` + ink text; active `soot` fill + white text.
- **Highlight span**: exactly ONE per headline — `cyan-edge` text on `sky-wash` pill background (padding ~2px 8px, radius 4px). Never in body paragraphs or nav.
- **Drawer**: right slide-in 420–480px, white surface, 1px left hairline `stone-border`, `--shadow-xl`, 24px padding; closes on overlay click/Esc.

### 3.5 Feedback
- Loading: inline spinner + 14px `warm-gray` status line ("Processing batch… Tier-2 cases may take ~30s"). Skeleton blocks: `stone-muted`/canvas stripes.
- Empty states: outline icon + one sentence + primary/ghost action pair. Never leave a blank panel.
- Errors: `status-danger` text on `#fef2f2` tint strip inside the relevant card, with recovery guidance ("Upload a .csv exported from…").

---

## 4. Voice & Content Guidelines

- Plain, calm, operator-to-operator English. Short sentences. No exclamation marks outside Hinglish previews.
- Explain rules where they appear: e.g., beside an AFA violation show "NPCI blocks silent auto-debits above Rs. 15,000" as 12px helper text.
- Money: `Rs.` prefix, en-IN digit grouping, integer rupees.
- Action names render humanized with the raw enum beneath in mono where audit precision matters: "Retry after backoff" / `RETRY_AFTER_BACKOFF`.
- Hinglish drafts render verbatim, styled as a preview card (see §5 MandateDetailDrawer) with a "DRAFT — would send via WhatsApp/SMS" caption.
- Escalation copy is reassuring, not alarmist: "Routed to your team — no further auto-actions will be taken."

---

## 5. Frontend Architecture (Phase 7)

### 5.1 Stack
Vite + React 18 + TypeScript (unchanged) · Tailwind v4 via `/theme.css` `@theme` (new) · react-router-dom v6 (new) · recharts · axios · react-dropzone · Fontsource Inter + Inter Tight.

### 5.2 Route Map

| Route | Page | Layout | Auth gate |
|---|---|---|---|
| `/` | Landing | MarketingLayout (top nav + footer) | public |
| `/docs` | Docs | MarketingLayout | public |
| `/login` | Login (onboarding) | AuthLayout (centered card) | public |
| `/app` | Dashboard (metrics overview) | AppShell (sidebar) | yes |
| `/app/batch` | Batch (upload + results) | AppShell | yes |
| `/app/audit` | Audit trail | AppShell | yes |

Five real pages + login. No more (anti-overengineering rule). Logout lives in the AppShell sidebar footer.

### 5.3 Layouts
- **MarketingLayout**: minimal top bar — logo glyph+wordmark left, centered nav links (Product→`/#how`, Docs, GitHub), right cluster: "Sign in" nav-link + cyan CTA "Open console" → `/login`. Warm-canvas background; 96px section rhythm; footer band on `soot` with muted links.
- **AuthLayout**: full-canvas centering, single flat card (radius 10, hairline, 24px pad): wordmark, heading-sm with one highlight span, form, helper line linking back to Docs. Shield mascot sticker allowed once here.
- **AppShell**: left sidebar (240px, canvas bg, 1px right hairline): logo, nav items (Overview, Batches, Audit trail) with 1px-stroke icons, bottom: env chip ("Test mode") + Sign out. Main region: top bar (page title subheading + contextual action) + content max-width 1200px, 24–32px gaps.

### 5.4 Page Specifications

**Landing `/`** — job: explain the product in one scroll, prove it works, drive to login.
1. Hero: eyebrow tag pill ("UPI Autopay × e-NACH recovery") → display headline w/ ONE highlight span ("compliance-first") → 16px subhead (what it does, who for) → dual CTA (cyan "Open console", ghost "Read the docs") → trust line (test-mode badge + star row analog: "Built on Razorpay Test Mode — zero live money").
2. Floating dashboard preview: framed screenshot/mock of the Overview page with tab-pill switcher (Overview / Decision trail / Override) — grayscale filter per §2.7.
3. How it works (`#how`): three feature cards in a row — "Tier-1 rules resolve instantly" (~70% deterministic), "Tier-2 LLM handles the rest" (allow-list constrained), "Compliance gate cannot be bypassed" — each with outline icon + 14px body.
4. Six failure categories: 3×2 grid of flat cards (code, root cause, correct action) — the intellectual core made visible.
5. Single testimonial-style block (pilot quote format) + compliance promise line ("violations reaching execution: 0 — asserted in tests").
6. Footer (inverted `soot`): logo, nav echoes, "Razorpay Test Mode only" disclaimer.

**Docs `/docs`** — job: make integration self-serve; content drawn from project-context (context.md, api.md, compliance.md).
Left anchor sidebar (sticky, 200px): Overview · Two-tier architecture · Compliance rules · CSV upload format · API reference · Actions allow-list. Right: single-column prose, heading-sm sections, code blocks as `soot` rounded cards with 13px mono, endpoint method+path pills. Include the six-category table, the four gate rules, curl examples for every endpoint, and the CSV column dictionary table.

**Login `/login`** — job: demo onboarding without backend auth.
Flat card: wordmark, "Sign in to Aegis" heading w/ highlight span, email + password fields (client-side validated), cyan CTA "Sign in", ghost "Continue as guest" (same result), helper text: "Demo build — sessions are local to your browser. API-key auth arrives with multi-tenancy (Phase 9)." Success sets a localStorage session flag and routes to `/app`. Wrong creds show an inline `status-danger` hint but still permit guest entry (demo-honest).

**App — Overview `/app`** — job: answer "how much did we recover and what needs a human?"
Row 1: four metric stats (Recovered / At risk / Recovery rate / Violations caught — context lines carry semantic color; violations stat appends "executed: 0 ✓"). Row 2: Tier split donut (recharts, `soot` + `sky-wash` slices — monochrome chart palette) + Recovery-by-category table (right-aligned %, category codes in mono). Row 3: Human review queue table with resolve buttons. Every panel: flat card + 13px helper explaining what the number means.

**App — Batch `/app/batch`** — job: upload CSV, watch decisions land, inspect any mandate.
State A (no batch): dropzone (dashed `stone-muted`, radius 16, hover `sky-wash`/5 tint) + "download sample CSV" ghost link + expected-format summary. State B (processing): spinner + honest timing note. State C (results): batch metrics stat row → compliance overrides section FIRST if any exist (each: warning-tinted card, struck-through proposed action, rule cited, final action, link into drawer) → mandate list table (ID short-mono, decline code, tier badge, proposed→final, outcome badge, ⚠ icon) → click opens MandateDetailDrawer (full decision trail, rationale/confidence, alternatives considered, HinglishMessagePreview card, razorpay response JSON collapsed, link to audit entry).

**App — Audit `/app/audit`** — job: immutable evidence trail.
Filter row (mono search by mandate id) + paginated table (timestamp, mandate id, tier, proposed→final, outcome badge, violation rule) + entry-count caption ("Append-only — entries can never be edited or deleted."). Pagination controls as pill group.

### 5.5 Auth Gate (demo scope)
`AppShell` wraps routes in an `AuthGuard`: reads localStorage `aegis_session`; missing → redirect `/login?next=…`. This is explicitly a **demo gate**; Phase 9 replaces it with API-key auth middleware. Documented in code comment + login page copy.

### 5.6 File Structure Additions

```
dashboard/src/
├── styles/
│   └── index.css            (imports ../theme.css? -> see note: theme.css copied to src/styles/theme.css)
├── lib/
│   ├── auth.ts              (session get/set/clear)
│   └── format.ts            (rupee/en-IN/date formatters, humanizeAction())
├── layouts/
│   ├── MarketingLayout.tsx
│   ├── AuthLayout.tsx
│   └── AppShell.tsx         (includes AuthGuard)
├── pages/
│   ├── Landing.tsx  Docs.tsx  Login.tsx
│   └── app/ Dashboard.tsx  Batch.tsx  Audit.tsx
├── components/ …            (existing 9, restyled to tokens)
└── types/, api/             (unchanged from original plan)
```
`theme.css` (repo root, Tailwind v4 `@theme`) is imported by Vite via `src/styles/index.css`; `variables.css` values are already mirrored inside it. Router setup lives in `main.tsx`.

---

## 6. Accessibility

- Contrast floor 4.5:1 for text: warm-gray (#78716c) on canvas = ~5.3:1 ✓; ash-gray reserved for ≥12px non-essential hints (3.4:1) — never for actionable labels.
- Focus rings: 2px `cyan-signal`, visible on ALL interactive elements; never removed.
- Drawer/modals: focus trap + Esc close + `aria-modal`.
- Status never conveyed by color alone: outcome badges pair color with text label; violation rows add ⚠ icon.
- Tables get `<th scope>` + caption-level summaries; charts get adjacent textual totals (tier counts printed beside donut).
- Full keyboard path: nav → uploader → table rows (Enter opens drawer) → drawer → resolve.

---

## 7. Do's and Don'ts (binding)

**Do**
- Background `#fafaf9`, cards `#ffffff` — never inverted.
- One cyan-filled CTA per viewport; everything else ghost.
- One highlight span per headline, on the value keyword.
- 1px stone borders as structure; shadows only per §2.2 elevation map.
- Body = 14px Inter 400/1.64; headings = Roobert-token 400 with negative tracking.
- Semantic status colors only as text/icon/tint per §2.3.
- Show raw enums alongside humanized labels in audit/detail contexts.
- Honest empty/loading/error states everywhere.

**Don't**
- No new accent hues, gradients, glassmorphism, or dark mode.
- No heavy shadows on ordinary cards (`--shadow-xl` is single-element-per-page).
- No headings in Inter; no bold-weight headings.
- No colored button fills other than cyan; no status-color page sections.
- More than one mascot/sticker appearance per section — forbidden.
- No live-money claims: test-mode disclaimers stay visible on landing footer and app sidebar.

---

## 8. Source File Mapping

| File | Role in implementation |
|---|---|
| `/theme.css` | Copy to `dashboard/src/styles/theme.css`; imported first in `index.css`; drives all Tailwind utilities. |
| `/variables.css` | Reference duplicate of tokens for non-Tailwind contexts; keep at root, do not import in the app (avoids drift). |
| `/tokens.json` | Machine-readable token export (W3C-style) for future tooling (Figma/plugin sync); not consumed at build time. |
| `/DESIGN.md` | Original style-reference prose; superseded by this document for Aegis-specific decisions. |

*Any deviation from this document during Phase 7 must be recorded in `project-context/progress.md` Decisions Made.*
