# Page design contract

Every page in AgentSDR is built the way `/analytics` and `/outreach/campaigns`
are built. This file is the checklist. The reference implementations to read
before building a page:

- `src/components/outreach/CampaignListClient.tsx` — a list page
- `src/components/outreach/CampaignDetailClient.tsx` + `AnalyticsTab.tsx` — a detail page
- `src/components/analytics/views/OverviewView.tsx` — dashboard cards
- `src/components/Sidebar.tsx` — navigation

## Building blocks

| Need | Use |
|---|---|
| Page width and padding | `PageContainer` (`./PageHeader`) |
| Title, description, badge, back link, actions | `PageHeader` |
| Page-level sections (Analytics / Leads / Sequence) | `PageTabs` |
| Live figures on a detail page ("today", "next send") | `StatRow` |
| Headline numbers | `KpiStrip` + `KpiCell` (`@/components/analytics/kit/KpiStrip`) |
| Any card | `Frame` + `FrameHeader` + `FramePanel` (`@/components/analytics/kit/Frame`) |
| Charts | `ChartCard`, `TimeSeriesChart`, `DonutChart`, `FunnelChart`, `BarList`, `SegmentedBar` from the Analytics kit |
| Nothing to show | `EmptyState` |
| Loading | `Skeletons` (`ListPageSkeleton`, `DetailPageSkeleton`, `SplitPaneSkeleton`, `TableSkeleton`, `Skeleton`) |
| Controls | AlignUI in `@/components/alignui/*`: `Button`, `Input`, `Select`, `SegmentedControl`, `Dropdown`, `Popover`, `Modal`, `Badge`, `Table`, `Tooltip`, `Pagination`, `Avatar` |

Do not hand-roll a card, header, tab bar, badge or empty state that one of
these already provides.

## Layout

- White page (`bg-bg-white-0`). Content sits in Frames: a grey outer frame
  that carries the header, a white inner panel that carries the content.
- A list page: `PageHeader` (primary action on the right) → optional
  `KpiStrip` of 3–5 numbers that answer "how is this going?" → one Frame
  holding the list, with filters and search in its header.
- A detail page: `PageHeader` with `back` and a status badge → `StatRow` →
  `PageTabs` → Frames.
- An inbox (split pane): header, then a list pane and a reading pane side by
  side filling the viewport height; the list pane scrolls on its own.
- Grids use `grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5`.
- Works at 390 px wide with no horizontal page scroll: wide tables go in an
  `overflow-x-auto` wrapper with a `min-w-[…]` on the table.

## Type and colour

- Title `text-title-h5`; card titles `text-label-sm`; descriptions
  `text-paragraph-xs`/`-sm text-text-sub-600`.
- Numbers are text tokens (`text-text-strong-950`, `tabular-nums`) — never
  link-blue, never the series colour.
- Primary actions are AlignUI `Button variant="primary"` (the blue). No
  indigo/purple/raw Tailwind palette colours (`bg-indigo-50`, `text-slate-600`,
  `bg-[#…]`) — use the tokens.
- Channel identity: `CHANNEL_META` in `@/components/analytics/theme`
  (Email orange, LinkedIn blue, WhatsApp green — `HUE` in theme.ts). Status colours
  (`STATUS`) only for good/warning/critical states, always with a label.

## Tables

- AlignUI `Table` inside `FramePanel className="p-2 sm:p-2"` (or `overflow-x-auto`).
- `Table.Head scope="col" className="px-4"`, cells `px-4`, `Table.Body spacing={4}`.
- First column: avatar/icon + name + one muted sub-line. Truncate long text
  and put the full value in `title`.
- A clickable row is also keyboard-reachable: `tabIndex={0}` and Enter opens
  it; cells holding their own buttons stop propagation.
- Status: AlignUI `Badge` `variant="lighter"` with `Badge.Dot`.
- Row actions: one ghost `…` button opening a `Dropdown`.
- No selection checkboxes unless a bulk action exists.
- Counts and dates right-aligned only when they are numeric columns.

## Filters

- ≤ 5 options with counts: `SegmentedControl` in the Frame header.
- More: AlignUI `Select`, or a `Popover` filter menu.
- Search: `Input size="small"` with `RiSearchLine`.

## States

- Route loading: a `loading.tsx` next to the page that renders the matching
  skeleton from `Skeletons`.
- Client fetch, first load: skeleton rows in place of the table/list.
- Client refetch: keep the old rows, dim them (`opacity-60`), `aria-busy`.
- Empty: `EmptyState` saying what is missing and what to do, with the action
  when there is one. "No matches" is different from "nothing yet".
- Errors: an inline `role="alert"` message with a retry where possible.

## Rules

- Keep every existing capability: each action, modal, API call and
  keyboard path still works. This is a redesign, not a rewrite of logic.
- Remove controls that do nothing.
- Every change should make the page easier to read or act on.
