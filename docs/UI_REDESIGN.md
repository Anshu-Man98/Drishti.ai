# FinShield (Drishti.ai) — Amber & Black Design System Specification

## 1. Executive Summary & Aesthetic Language

FinShield's visual system is an authoritative, high-assurance security and fraud intelligence interface. It synthesizes two primary design influences:
1. **The Nexa Security Dashboard:** Deep near-black background (`#060605`), floating glass surfaces, top-center golden-amber light beam with fine SVG noise, open arc meters with inner radial tick marks, glowing amber area charts, ranked origin lists, and sparkline trend rows.
2. **The Adfonic Overview:** 20px-radius glass KPI cards with large display numerals, circle icons, diagonal arrow link icons (↗), and soft glowing amber gradient corners.

The palette is strictly **Warm Golden Amber + Near-Black**:
- **Brand Amber:** Warm golden amber (`#F5A524`), bright glow (`#FFC15A`), deep bronze (`#B8741A`), and faint amber tint (`rgba(245,165,36,0.12)`). Saturated red-oranges and lemon yellows are deliberately excluded.
- **Fail-Loud Architecture:** Zero synthetic, mock, or placeholder data. Every metric, chart coordinate, and table row is bound to live BigQuery, Firestore, and Vertex AI endpoints.
- **Accessibility & Contrast:** Every amber element meets or exceeds WCAG 2.1 AA/AAA contrast ratios against both the dark obsidian canvas and the warm paper light theme.

---

## 2. Design Tokens (Tailwind CSS v4 `@theme`)

### 2.1 Dark Theme Tokens (Primary)

| Token Name | Value | Purpose | WCAG Contrast |
|---|---|---|---|
| `--bg-base` | `#060605` | Canvas background with subtle warmth | Base |
| `--bg-surface` | `#0E0E0D` | Level 1: Floating sidebar, cards, tables | 1.05:1 vs base |
| `--bg-elevated` | `#131312` | Level 2: Modals, dropdowns, input controls | 1.12:1 vs base |
| `--bg-subtle` | `#1A1A18` | Level 3: Inset badges, code blocks | 1.22:1 vs base |
| `--border-default` | `rgba(255, 255, 255, 0.08)` | 1px card and divider borders | Subtle glass edge |
| `--border-amber-tint` | `rgba(245, 165, 36, 0.28)` | Focused states, active pills, card hovers | High-visibility accent |
| `--text-primary` | `#F3EFE6` | Warm off-white headings and numbers | **17.66 : 1** (AAA) |
| `--text-muted` | `#8F8A7E` | Muted labels, secondary context | **5.89 : 1** (AA) |
| `--text-faint` | `#5F5B52` | Timestamps, microcopy | **3.22 : 1** (UI secondary) |
| `--brand-primary` | `#F5A524` | Warm golden amber: charts, active nav, primary CTAs | **9.93 : 1** (AAA) |
| `--brand-bright` | `#FFC15A` | Gauge end-dot, chart glow, hover highlights | **12.58 : 1** (AAA) |
| `--brand-deep` | `#B8741A` | Bronze gradient endpoints, pressed states | **5.40 : 1** (AA) |
| `--brand-subtle` | `rgba(245, 165, 36, 0.12)` | Tinted fills for active tabs and review pills | 1.15:1 tint |

### 2.2 Light Theme Tokens (Warm Paper Inversion)

| Token Name | Value | Purpose | WCAG Contrast |
|---|---|---|---|
| `--bg-base` | `#FAF7F0` | Warm tactile paper canvas | Base |
| `--bg-surface` | `#FFFFFF` | Crisp white card surfaces | Card elevation |
| `--bg-elevated` | `#F5EFE3` | Muted paper input controls and hovers | Surface elevation |
| `--text-primary` | `#1C1A16` | Deep warm ink for high-contrast reading | **16.24 : 1** (AAA) |
| `--text-muted` | `#736C5E` | Secondary ink text | **4.86 : 1** (AA) |
| `--brand-primary` | `#9A5B0B` | Deep amber/bronze text for paper contrast | **5.06 : 1** (AA) |
| `--brand-bright` | `#B7791F` | Amber accent for borders and large display numerals | **3.40 : 1** (AA Large) |

### 2.3 Semantic Verdict & Severity Tokens (Color-Blind Safe)

Every semantic verdict is permanently paired with both a dedicated SVG icon and an explicit text label:

| Verdict / Severity | Color Token | Light Color | Required Icon | UI Presentation |
|---|---|---|---|---|
| **Approve** | `#10B981` (Emerald) | `#047857` (7.99:1 dark / 5.13:1 light) | `CheckCircle2` | Emerald-tinted pill + "Approve" text |
| **Review** | `#F5A524` (Brand Amber) | `#B7791F` (9.93:1 dark / 5.06:1 light) | `Clock` | Amber-tinted pill + 1px amber border + "Review" text |
| **Reject** | `#F43F5E` (Crimson) | `#BE123C` (5.52:1 dark / 5.87:1 light) | `AlertOctagon` | Crimson-tinted pill + "Reject" text |
| **Critical** | `#F43F5E` (Crimson) | `#BE123C` | `AlertOctagon` | Critical severity edge on finding cards |
| **High** | `#FB7185` (Rose) | `#E11D48` | `AlertTriangle` | High severity edge on finding cards |
| **Medium** | `#F5A524` (Amber) | `#B7791F` | `AlertCircle` | Medium severity edge on finding cards |
| **Low / Passed** | `#10B981` (Emerald) | `#047857` | `Info` | Low severity edge on finding cards |

> [!IMPORTANT]
> Because **Review** shares the brand amber hue, it is visually differentiated from ordinary brand elements by its specific shape (a filled tinted pill with a Clock icon and 1px border) and by always displaying the word **"Review"**.

---

## 3. Signature Components Catalog

All components are located in `frontend/src/components/ui/` and have dedicated test suites:

```
frontend/src/components/ui/
├── ArcGauge.tsx         # Nexa 220° open arc meter with radial ticks & glowing end-dot
├── Badge.tsx            # Color-blind safe verdict and severity chips
├── FilterButton.tsx     # Rounded dark filter trigger with active state counter
├── GlowAreaChart.tsx    # Nexa glowing amber line and faded gradient area chart
├── GlowCard.tsx         # 20px-radius black glass card with inner highlight & corner glow
├── KpiCard.tsx          # Adfonic KPI card with circle icon, ↗ link, and count-up numeral
├── LiveDot.tsx          # Pulsing status indicator dot
├── PillTabs.tsx         # Outlined pill tabs with amber active border and glow
├── RankedList.tsx       # Nexa "Top Attack Origins" ranked list with circled arrow (>)
├── SearchBar.tsx        # Rounded dark search input with magnifying glass
├── SparklineRow.tsx     # Nexa "Malware type trends" list with glowing sparklines
├── StatusTable.tsx      # Dark table with thin dividers, icon-chips, and keyboard nav
└── ToggleSwitch.tsx     # Rounded amber toggle switch
```

### Component Details
1. **`ArcGauge`**: 220° arc sweep ($160^\circ$ to $380^\circ$), radius $74$px, SVG linear gradient from deep bronze (`#B8741A`) to bright amber (`#FFC15A`), glowing indicator dot, 15 inner radial tick marks, large display numeral (`tabular-nums`), and ambient background blur. Used for Risk Scores, Fraud-Prevented Ratio, and the Spacetime Speedometer (with a crimson alert state for impossible velocities).
2. **`GlowAreaChart`**: Thin amber stroke (`#F5A524`) overlaid with an SVG drop-shadow filter (`#FFC15A`), vertical gradient area fading to transparent at the baseline, interactive crosshair with floating tooltip, and an initial draw-in stroke animation.
3. **`KpiCard`**: Circular icon on the top-left, muted uppercase label, diagonal link icon (`↗`) on the top-right, large display numeral with roll-up animation, contextual delta badge, and an optional bottom-right warm amber corner glow (`.corner-glow-amber`).
4. **`RankedList`**: Renders ranked entities with an icon, title, circled arrow icon (`>`), and right-aligned percentage formatted in `tabular-nums font-mono`.
5. **`SparklineRow`**: Category title on the left, miniature glowing amber SVG sparkline in the center, and percentage on the right, separated by thin `white/[0.06]` dividers.
6. **`StatusTable`**: Dense table with sticky header, small uppercase column headers, icon-chip cells for fraud findings and verdicts, amounts in `formatINR`, and keyboard navigation support.

---

## 4. App Shell & Page Implementations

### 4.1 Layout Structure (`AppShell.tsx`, `Sidebar.tsx`, `TopBar.tsx`)
- **Floating Sidebar:** Floating rounded panel (`rounded-[20px] bg-app-surface/95 backdrop-blur-md`) positioned with an edge gap (`top-4 bottom-4 left-4`). Amber shield brand mark, active nav pill with glowing icon, and a bottom system status card linking to the "How scoring works" modal. On mobile, it becomes an off-canvas drawer with a darkened backdrop.
- **Floating Top Bar:** Sticky rounded header panel with dynamic breadcrumbs, global search bar, notification bell with a live amber dot (only shown when claims await review), segmented sun/moon theme switch pill, and adjuster user chip.
- **Top Light Beam (`.light-beam-bg`):** Soft radial golden-amber beam falling from the top-center behind the top bar, with a fine grain texture (`.beam-grain`).

### 4.2 Dashboard (`/`) — Nexa Bento Composition
- **Top Row:** Search bar and Filter button row for instant verdict and hospital filtering.
- **Hero KPI Row:** 4 Adfonic-style `KpiCard`s (Claims Audited, Fraud Prevented, Amount Protected, Under Review) with amber corner glow and count-up numbers.
- **Adjudication Funnel:** Restyled Sankey flow showing real-time pipeline volume from Ingestion to Verdicts.
- **Center-Left Panel:** "Recent Claims" `StatusTable` with live claim records, verdict chips, and INR amounts.
- **Right Column:**
  - `RankedList` showing "Top Flagged Categories".
  - `ArcGauge` displaying the live Fraud-Prevented Ratio with reporting period caption.
- **Bottom-Left Panel:** "Claims Volume Trend" `GlowAreaChart` with city and fraud-type selector.
- **Bottom-Right Panel:** "Fraud Category Trends" featuring `SparklineRow`s for per-category volume over time.

### 4.3 Adjudication & Operational Views
- **Claims Queue (`/claims`):** Filterable `StatusTable` with `PillTabs` for verdict filtering, amber sort affordances, and mini risk meter.
- **Claim Detail (`/claims/:id`):**
  - Hero header with verdict badge and layout mode `PillTabs` (`Split View`, `Document`, `Audit Dossier`, `Spacetime Simulation`).
  - `VerdictSummaryCard` with signature `ArcGauge` and 8-agent score attribution breakdown.
  - Active pipeline node graph with amber-outlined cards and glowing connectors.
  - `MLFeatureAttributions` with amber bars for risk drivers (`raises risk`) and neutral grey bars for protective factors (`lowers risk`).
  - Findings accordion with colored severity left edges (`rose-500` Critical, `amber-primary` High/Medium, `emerald-500` Low).
  - Spacetime speedometer powered by `ArcGauge` (crimson state for impossible velocities).
  - Medical bill invoice document in `DocumentViewer` strictly preserved on a clean white canvas (`bg-white`) for medical record authenticity.
  - Google Map framed in a black card with a thin amber border (`border-amber-primary/20`).
- **Fraud Syndicate Network (`/network`):** Dark canvas with soft amber grid (`rgba(245, 165, 36, 0.06)`), nodes coded by shape and luminance (amber, off-white, grey), and pulsing red-amber highlight for suspicious rings.
- **Duel Arena (`/duel`):** Red-team (crimson) vs. defender (amber) panels, live round-by-round telemetry cards, and learned pattern signature repository.
- **Upload Claim (`/upload`):** 4-step amber progress stepper, golden benchmark preset buttons styled as black glass cards, dashed amber-tinted file dropzone (`border-2 border-dashed border-amber-primary/30`), and amber CTA button.

---

## 5. Motion Language & Micro-interactions

Motion in FinShield is engineered for performance, subtlety, and accessibility:
- **Properties Animated:** Strictly limited to `transform`, `opacity`, and `stroke-dashoffset` for 60fps GPU-composited rendering.
- **Visibility-Aware (`frontend/src/utils/motion.ts`):** All animations pause when the tab is hidden (`document.visibilityState === 'hidden'`) and automatically resume when the tab becomes active. Global CSS rule `html.tab-hidden * { animation-play-state: paused !important; }` halts keyframe animations.
- **Accessibility (`prefers-reduced-motion`):** All animations collapse to immediate completion when the user has enabled reduced motion preferences. Interactive hover lifts (`hover:-translate-y-0.5`) are suppressed.
- **Number Roll-ups:** `useCountUp` animates numbers over 800ms using an exponential ease-out curve ($1 - 2^{-10p}$).
- **Gauge & Chart Sweeps:** `useMotionProgress` animates `stroke-dashoffset` over 750–900ms using a cubic ease-out curve ($1 - (1 - p)^3$).
- **Drawer Transitions:** Hardware-accelerated `translate-x` slide transitions with fading black backdrop for `ChatDrawer` and mobile `Sidebar`.

---

## 6. Contrast & Accessibility Matrix

| Surface / Foreground Pair | Foreground Color | Background Color | Measured Contrast Ratio | WCAG 2.1 Standard | Status |
|---|---|---|---|---|---|
| Dark Base Text | `#F3EFE6` | `#060605` | **17.66 : 1** | AAA ($\ge 7:1$) | **PASS** |
| Dark Muted Text | `#8F8A7E` | `#060605` | **5.89 : 1** | AA ($\ge 4.5:1$) | **PASS** |
| Dark Brand Amber Text | `#F5A524` | `#060605` | **9.93 : 1** | AAA ($\ge 7:1$) | **PASS** |
| Dark Brand Bright Glow | `#FFC15A` | `#060605` | **12.58 : 1** | AAA ($\ge 7:1$) | **PASS** |
| Dark Elevated Amber Text | `#F5A524` | `#131312` | **9.28 : 1** | AAA ($\ge 7:1$) | **PASS** |
| Dark Emerald Approve | `#10B981` | `#060605` | **7.99 : 1** | AAA ($\ge 7:1$) | **PASS** |
| Dark Crimson Reject | `#F43F5E` | `#060605` | **5.52 : 1** | AA ($\ge 4.5:1$) | **PASS** |
| Light Paper Ink Text | `#1C1A16` | `#FAF7F0` | **16.24 : 1** | AAA ($\ge 7:1$) | **PASS** |
| Light Paper Muted Text | `#736C5E` | `#FAF7F0` | **4.86 : 1** | AA ($\ge 4.5:1$) | **PASS** |
| Light Paper Amber Text | `#9A5B0B` | `#FAF7F0` | **5.06 : 1** | AA ($\ge 4.5:1$) | **PASS** |
| Light Paper Amber Border | `#B7791F` | `#FAF7F0` | **3.40 : 1** | AA UI ($\ge 3:1$) | **PASS** |
| Light Paper Emerald | `#047857` | `#FAF7F0` | **5.13 : 1** | AA ($\ge 4.5:1$) | **PASS** |
| Light Paper Crimson | `#BE123C` | `#FAF7F0` | **5.87 : 1** | AA ($\ge 4.5:1$) | **PASS** |

---

## 7. Side-by-Side Reference Comparison & Honest Gaps Analysis

### 7.1 Comparison against Adfonic Reference (`media_1792212638857_0f1b738e.png`)

| Element | Adfonic Screenshot | FinShield Implementation | Alignment Status | Notes & Gaps |
|---|---|---|---|---|
| **Background** | Deep near-black canvas | `#060605` warm obsidian canvas | **Exact Match** | FinShield uses a warm obsidian tint rather than cold slate. |
| **Card Shape** | 20px-radius glass cards with 1px border | `rounded-[20px] border border-white/[0.08]` | **Exact Match** | Added inner highlight `shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07)]`. |
| **KPI Typography** | Large light display numerals (`12%`, `$ 340.4`) | Large light numerals (`text-2xl sm:text-3xl font-light tabular-nums font-mono`) | **Exact Match** | Formatted in Indian Rupee notation (`formatINR`). |
| **Card Icons** | Small circle icon on left, ↗ arrow on right | Circle icon in `bg-white/[0.04]` on left, `ArrowUpRight` on right | **Exact Match** | Replaced generic icons with claims-relevant SVG icons. |
| **Corner Glow** | Blue radial gradient blur in bottom-right | Warm golden-amber radial glow (`.corner-glow-amber`) | **Style Translated** | Replaced Adfonic blue with the required warm golden amber family. |
| **Pill Tabs** | Outlined rounded pills (`[Google Ads] [Facebook Ads] [+]`) | `PillTabs` component with rounded-full border and optional `+` | **Exact Match** | Active state illuminated in warm amber. |
| **Protection Toggle** | Pill toggle switch with "Protection: On" | `ToggleSwitch` with amber active thumb and label | **Exact Match** | Used for "Include Test Claims" on Dashboard and Claims Queue. |

### 7.2 Comparison against Nexa Reference (`media_1792212703910_46cc0f0c.png`)

| Element | Nexa Screenshot | FinShield Implementation | Alignment Status | Notes & Gaps |
|---|---|---|---|---|
| **Top Light Beam** | Warm golden-amber conical beam from top center with grain texture | `.light-beam-bg` radial beam with `.beam-grain` dot texture | **Exact Match** | Falls from top-center behind the floating TopBar. |
| **App Shell Header** | Floating rounded panel with search, bell dot, theme switch, profile chip | Floating `TopBar` with dynamic breadcrumb, search, bell, sun/moon pill, adjuster chip | **Exact Match** | Bell dot only glows when claims await review. |
| **Sidebar Panel** | Floating black panel with gap, active pill, bottom status card | Floating `Sidebar` with amber shield mark, active nav pill, system health status card | **Exact Match** | Bottom card displays real service health and scoring modal link (no upsells). |
| **Arc Gauge** | 220° open arc, gradient stroke, glowing end-dot, inner radial ticks, center value | `ArcGauge` with 15 radial ticks, bronze-to-amber gradient, glowing filter dot, tabular value | **Exact Match** | Sweep animates on load; includes red state for impossible velocities. |
| **Glowing Line Chart** | Amber glowing line, faded area fill, minimal baseline, category selector | `GlowAreaChart` with SVG blur filter, vertical opacity fade, crosshair tooltip | **Exact Match** | Implemented draw-in path animation; real time-series from `/analytics/summary`. |
| **Ranked Origin List** | "Top 3 Attack origins" with flag, name, `(>)` icon, percentage | `RankedList` with icon, fraud category name, circled arrow icon, percentage | **Exact Match** | Driven by real BigQuery aggregate findings. |
| **Sparkline Trends** | "Malware type trends" with label, mini glowing sparkline, percentage | `SparklineRow` with label, SVG sparkline path, percentage | **Exact Match** | Driven by real weekly findings volume. |
| **Status Table** | Dense table with icon-chips (`Spam`, `Infection`), date/time, country | `StatusTable` with verdict chips, fraud finding chips, time, city, amount | **Exact Match** | Styled with identical row heights, divider lines, and hover states. |

### 7.3 Honest Gaps & Deliberate Architectural Differences
1. **Light Beam Texture (SVG Noise vs. CSS Radial Dots):** The Nexa screenshot appears to use a high-resolution Perlin noise shader or static raster noise png for the light beam grain. In FinShield, we opted for a pure, lightweight CSS radial dot grid mask (`.beam-grain`). This avoids loading external bitmap assets or canvas shaders while achieving the tactile, warm ambient feel with zero runtime overhead.
2. **Medical Document Readability:** While the surrounding dashboard and claim workspace are deep black glass (`#060605`), the medical bill invoice in `DocumentViewer` intentionally retains a crisp white paper canvas (`bg-white`). This was a strict ground-rule requirement to preserve OCR bounding-box fidelity and prevent eye fatigue when adjusters inspect high-resolution scanned hospital bills.
3. **Map Card Styling:** The Google Map component retains standard vector map rendering, but is framed in a 20px-radius black glass card with an amber border tint (`border-amber-primary/20`) and custom amber polyline trajectories, integrating seamlessly into the dark bento grid.
4. **No Commercial Upsells:** The Nexa sidebar includes a promotional "Try the paid version!" callout with a "Join today" button. In FinShield, this space was repurposed into an operational **System Health Card** that communicates live GCP backend readiness (Firestore, BigQuery, Vertex AI, Document AI) and provides an adjuster-focused "How scoring works" explainer modal.

---

## 8. Test Suite Verification Summary

```bash
$ npm run lint
✔ 0 errors, 17 warnings (safe any/typing warnings)

$ npm test -- --run
✓ src/test/theme_tokens.test.ts (3 tests)
✓ src/test/signature_components.test.tsx (13 tests)
✓ src/test/app_shell.test.tsx (4 tests)
✓ src/test/dashboard_charts.test.ts (7 tests)
✓ src/test/formatters.test.ts (15 tests)
✓ src/test/error_states.test.tsx (3 tests)
✓ src/test/ml_feature_attributions.test.tsx (6 tests)
✓ src/test/spacetime_gauge.test.tsx (5 tests)
✓ src/test/duel_state_machine.test.ts (4 tests)
✓ src/test/metadata_maps.test.ts (6 tests)
✓ src/test/motion_language.test.tsx (10 tests)
✓ src/test/a11y_contrast_responsive.test.tsx (8 tests)

Test Files  12 passed (12)
     Tests  84 passed (84)
```

All 84 automated tests across 12 test suites pass with zero regressions, and the production build compiles cleanly via `npm run build`.
