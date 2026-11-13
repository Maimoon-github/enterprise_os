# Enrichment layer ("Clay in AgentSDR")

The plan for building a Clay-style enrichment grid as a first-class part of this
app, alongside the outreach, LinkedIn and CRM systems that already exist — and
then open-sourcing the whole thing under AGPL-3.0 so anyone can self-host it.
(Licence changed to MIT on 8 October 2026; the AGPL notes below are kept as the
record of the original decision. No Teable code was ever copied in.)

Read `CLAUDE.md` first. This document assumes its conventions (Drizzle only,
`scripts/` as migration history, TypeScript everywhere) and does not restate them.

---

## 1. What this is, and what it is not

The end state is one app that does the whole GTM loop:

```
  build a list  →  enrich it  →  push to outreach  →  replies land in CRM
  └──────── new ────────┘         └──────── already exists ────────┘
```

The enrichment layer is the missing left half. It is a table UI where each column
can be static data, an API call, an AI prompt, or a waterfall across several
providers — and each cell runs independently, asynchronously, and costs money.

**It is not a spreadsheet.** This distinction drives the entire architecture and
is the single most important thing in this document, so it gets its own section.

---

## 2. The core insight: it's a column DAG, not a spreadsheet

Clay looks like a spreadsheet, which invites the assumption that we need a
spreadsheet engine. We do not, and adopting one would be an expensive mistake.

| Real spreadsheet (Excel, Sheets) | Clay-style enrichment grid |
| --- | --- |
| The **cell** is the unit of computation | The **column** is the unit |
| `A1` may reference `B7` — arbitrary 2D references | A column references *other columns, same row only* |
| Formulas are pure and evaluate instantly | Cells are async API calls: seconds long, and billed |
| Recalculation is synchronous | Each cell is a durable job with `pending` / `running` / `error` / `success` |
| Dependency graph spans every cell (millions of nodes) | Dependency graph spans columns (~30 nodes), replayed per row |

You will never see `=SUM(A1:A10)` in Clay. Every column is `f(other columns of
this row)`. That restriction is a gift: the dependency graph is tiny and fixed
per table, and it fans out identically across every row.

Two direct consequences:

- **No spreadsheet engine.** HyperFormula is the obvious candidate and is the
  wrong tool — it solves 2D cell-reference recalculation, a problem we don't
  have. (Its GPLv3 licensing would have been a blocker under most licenses; it
  happens to be compatible with our AGPL choice, which makes this a judgement
  call rather than a forced one. We are still declining it, on the grounds of
  fit rather than licence.) A single-row scalar expression evaluator is a few
  hundred lines and is deferred to a later phase anyway.
- **The DAG is cheap to compute.** Topologically sort ~30 columns once, then
  reuse that order for all 50,000 rows.

---

## 3. Decisions, and why

These were settled before planning and are treated as fixed. Recorded here with
rationale so the reasoning survives.

| Decision | Choice | Why |
| --- | --- | --- |
| Licence | **AGPL-3.0** | Self-hosting stays free; anyone offering it as hosted SaaS must open their changes. Category standard (Teable, Baserow). |
| Tenancy | **Single-tenant** | No `users`/`orgs` tables exist today; auth is one shared password. One deployment = one team. Avoids a refactor across 35 tables. |
| Job engine | **Postgres-only, in-process** | Keeps self-host at `docker run` + `DATABASE_URL`. No Redis, no cloud dependency. |
| Integration | **Grid enriches, then pushes** | Existing outreach/CRM tables untouched; one well-defined mapping step at the seam. |
| Scale target | **≤ 50k rows per table** | JSONB storage is comfortably fast at this size with expression indexes. |
| Cost tracking | **Full per-cell** | BYOK users still spend real money per call. Cost-ordering the waterfall *is* the feature. |
| Live updates | **Polling** | Works behind any reverse proxy, zero extra infra. Costs a second of latency. |
| v1 runners | **HTTP, AI, Waterfall** | LinkedIn/Unipile and Formula deferred — see Phase 6. |

### What the licence choice unlocks

AGPL means we may read and borrow from Teable (also AGPL) where useful. We are
still **not** adopting Teable wholesale: it is a separate NestJS application, so
running it means running a second app — which defeats the single-app goal — and
it is an Airtable clone. It has formulas and rollups but no waterfall, no
provider orchestration, no cost accounting. That missing layer is precisely the
part that makes this Clay rather than Airtable.

---

## 4. Storage: JSONB rows, not dynamic DDL

Three candidate models were considered.

**Physical Postgres columns per user column** — the Teable model. Real typed
columns, real indexes, excellent at millions of rows. Rejected: it requires
runtime `ALTER TABLE` on user action, which collides head-on with the convention
in `CLAUDE.md` that `scripts/` is the hand-maintained record of schema history.
User-created tables would live entirely outside the migration story, and
`drizzle.config.ts`'s `tablesFilter` allowlist would become meaningless.

**EAV, one row per cell** — 50 columns × 50k rows = 2.5M rows per table, and
every read becomes a pivot. Rejected on both performance and ergonomics.

**One JSONB blob per row** — chosen. It also matches a pattern this codebase has
already committed to: `outreach_leads.customFields` is a JSONB bag keyed by CSV
header, resolvable as `{{token}}` in a sequence. The enrichment grid is a
generalisation of something that already works here.

### Schema

New file, `src/lib/grid/schema.ts`, re-exported from `src/lib/schema.ts`
alongside the existing domain schemas.

```ts
/** One user-created table. */
export const gridTables = pgTable("grid_tables", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  description: text("description"),
  /** Master switch behind the "Auto-run" toggle. */
  autoRun: boolean("auto_run").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
});

/** One user-defined column. `config` holds the runner spec. */
export const gridColumns = pgTable("grid_columns", {
  id: uuid("id").primaryKey().defaultRandom(),
  tableId: uuid("table_id").notNull()
    .references(() => gridTables.id, { onDelete: "cascade" }),
  /** Stable JSONB key. Generated once, NEVER renamed. */
  key: text("key").notNull(),
  /** Display label. User-renameable, cosmetic only. */
  name: text("name").notNull(),
  type: text("type").notNull().$type<ColumnType>(),
  config: jsonb("config").$type<ColumnConfig>().default({}),
  /** Column keys this one reads — the DAG edges. Derived, never hand-set. */
  dependsOn: text("depends_on").array().notNull().default([]),
  position: doublePrecision("position").notNull(),
  autoRun: boolean("auto_run").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
}, (t) => [unique("grid_columns_table_key_uq").on(t.tableId, t.key)]);

/** One row. All user data lives in `cells`. */
export const gridRows = pgTable("grid_rows", {
  id: uuid("id").primaryKey().defaultRandom(),
  tableId: uuid("table_id").notNull()
    .references(() => gridTables.id, { onDelete: "cascade" }),
  /** Fractional index — reorder/insert without renumbering neighbours. */
  position: doublePrecision("position").notNull(),
  /** { [columnKey]: value } — the value plane. */
  cells: jsonb("cells").$type<Record<string, unknown>>().notNull().default({}),
  /** { [columnKey]: { status, error, provider, costCents } } — the metadata plane. */
  cellMeta: jsonb("cell_meta").$type<Record<string, CellMeta>>().notNull().default({}),
  /** Monotonic, bumped on every write. The polling cursor — see §7. */
  version: bigint("version", { mode: "number" }).notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
});
```

Three details that matter more than they look:

**`key` vs `name`.** The JSONB is keyed by the immutable `key`; `name` is only a
label. Renaming a column touches one row in `grid_columns` instead of rewriting
50,000 JSONB blobs. Skip this and every rename becomes a migration.

**`cellMeta` as a sibling plane.** Every cell carries state beyond its value:
run status, error text, which provider hit, what it cost. Storing
`{ value, status, error }` inline triples JSONB size and makes every read of the
actual data awkward. Keep the value plane clean.

**`version` rather than `updatedAt` for polling.** A monotonic counter has no
clock skew and no ties, so `WHERE version > :cursor` is exact. Timestamps are
not, especially with sub-second job completion.

### Indexing

No DDL per user column is needed; expression indexes cover the hot paths:

```sql
CREATE INDEX grid_rows_table_pos_idx ON grid_rows (table_id, position);
CREATE INDEX grid_rows_table_version_idx ON grid_rows (table_id, version);
-- add per-table as needed, e.g. dedupe on email:
CREATE INDEX grid_rows_email_idx ON grid_rows ((cells->>'email'));
```

---

## 5. Execution: a Postgres work queue

### The constraint this must respect

`src/lib/outreach/internalScheduler.ts` says plainly:

> Safe ONLY because this app always runs as a single long-lived instance
> (confirmed — no horizontal scaling); nothing here claims a distributed lock.

That pattern does **not** extend to enrichment. Outreach ticks are deliberately
slow — one send per mailbox per minute, rate-limited by design. Enrichment wants
to fan out hundreds of concurrent API calls. Same process, opposite workload.

So we keep the *philosophy* (in-process, Postgres-only, started from
`instrumentation.ts`) and replace the *mechanism* with a proper claimed queue.

### The queue

```ts
export const gridJobs = pgTable("grid_jobs", {
  id: uuid("id").primaryKey().defaultRandom(),
  tableId: uuid("table_id").notNull(),
  rowId: uuid("row_id").notNull(),
  columnKey: text("column_key").notNull(),
  status: text("status").notNull().default("queued")
    .$type<"queued" | "running" | "done" | "error" | "cancelled">(),
  priority: integer("priority").notNull().default(0),
  attempts: integer("attempts").notNull().default(0),
  maxAttempts: integer("max_attempts").notNull().default(3),
  runAfter: timestamp("run_after", { withTimezone: true }).defaultNow(),
  lockedAt: timestamp("locked_at", { withTimezone: true }),
  error: text("error"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
}, (t) => [
  unique("grid_jobs_cell_uq").on(t.rowId, t.columnKey),
  index("grid_jobs_claim_idx").on(t.status, t.runAfter),
]);
```

Claiming uses `FOR UPDATE SKIP LOCKED`, the standard Postgres queue pattern:

```sql
UPDATE grid_jobs SET status = 'running', locked_at = now(), attempts = attempts + 1
WHERE id IN (
  SELECT id FROM grid_jobs
  WHERE status = 'queued' AND run_after <= now()
  ORDER BY priority DESC, created_at
  FOR UPDATE SKIP LOCKED
  LIMIT $1
)
RETURNING *;
```

**This is strictly safer than the existing scheduler.** `SKIP LOCKED` gives us
exactly the distributed lock `internalScheduler.ts` notes it lacks. If a
self-hoster ever runs two instances, the enrichment layer survives it correctly —
the outreach scheduler still would not. Worth knowing when that constraint is
eventually revisited.

The unique constraint on `(rowId, columnKey)` means a cell can only be queued
once. Re-running a cell updates the existing job rather than stacking duplicates.

### The worker

A pool inside the Next process, started from `instrumentation.ts` next to the
outreach scheduler:

- **Global concurrency cap** (`GRID_WORKER_CONCURRENCY`, default 10)
- **Per-provider semaphore**, so one slow provider can't starve the pool and
  each provider's own rate limit is respected
- **Exponential backoff** on retry via `runAfter`
- **Crash recovery**: on boot, reset `status='running'` jobs whose `lockedAt` is
  older than a timeout back to `queued`

### The cascade

When a cell completes, its dependent columns for *that row* become runnable.
That cascade is what the "Auto-run" toggle controls:

```ts
async function onCellComplete(rowId: string, columnKey: string) {
  const dependents = columnsDependingOn(columnKey);       // from the DAG
  const ready = dependents.filter((c) => c.autoRun && depsSatisfied(c, rowId));
  await enqueue(ready.map((c) => ({ rowId, columnKey: c.key })));
}
```

Cycles are rejected at column-save time, not discovered at runtime.

---

## 6. Column runners

Every entry in the "Add column" menu reduces to one interface:

```ts
interface ColumnRunner<C = unknown> {
  /** Which column keys this config reads → populates dependsOn, builds the DAG. */
  resolveDeps(config: C): string[];
  /** Execute for one row. */
  run(config: C, row: Record<string, unknown>, ctx: RunContext): Promise<CellResult>;
  /** Pre-run cost estimate, in cents, shown before the user commits. */
  estimateCost(config: C): number;
}

type CellResult = {
  value: unknown;
  provider?: string;
  outcome: "hit" | "miss" | "error" | "skipped";
  costCents: number;
};
```

Static types (`text`, `number`, `date`, `url`, `email`, `boolean`, `select`) have
no runner — they are plain stored values.

### v1 runners

**HTTP / REST** — highest leverage per unit of work, and therefore first. A
user-configured request with `{{column}}` interpolation, plus a JSON path to
extract from the response. This is the universal escape hatch: any self-hoster
can wire up any provider we never built. Ship this and the tool is useful to
people whose providers we've never heard of.

**AI / prompt** — a prompt template over other columns, with schema-constrained
JSON output. Mostly wiring, since `openai` is already a dependency. Model choice
per column; cost derived from token usage.

**Waterfall** — see below. The reason anyone chooses this category of tool.

### Provider credentials, and why they stay in env

Providers are registered in a `grid_providers` table, but **credentials are
never stored in the database** — the row holds the *name* of an environment
variable, and the worker reads `process.env` at call time.

This matters more for an open-source tool than a private one: self-hosters share
database dumps, post them in issues, and restore them into staging. Keys in
Postgres leak that way. Keys in env do not. The cost is that adding a provider
needs a container restart, which is an acceptable trade for single-tenant
deployments and matches how everything else in this app is already configured.

---

## 7. Waterfall and cost accounting

The waterfall is just another runner that internally calls other runners — which
is what makes the whole architecture hold together rather than needing a special
case.

```ts
type WaterfallConfig = {
  steps: Array<{ providerKey: string; config: unknown }>;
  /** Stop the row once cumulative spend crosses this. Prevents runaway cost. */
  maxCostCentsPerRow?: number;
};
```

Semantics: run steps in order, stop at the first non-empty result, record which
provider hit and what the attempt cost — including the misses, which are charged
too. Ordering cheapest-and-most-reliable first is the entire optimisation, and
users can only tune it if we show them the data.

Every attempt is appended to an audit table:

```ts
export const gridCellRuns = pgTable("grid_cell_runs", {
  id: uuid("id").primaryKey().defaultRandom(),
  tableId: uuid("table_id").notNull(),
  rowId: uuid("row_id").notNull(),
  columnKey: text("column_key").notNull(),
  provider: text("provider"),
  outcome: text("outcome").notNull().$type<"hit" | "miss" | "error" | "skipped">(),
  /** Fractions of a cent are normal — numeric, not integer. */
  costCents: numeric("cost_cents", { precision: 12, scale: 6 }).notNull().default("0"),
  latencyMs: integer("latency_ms"),
  request: jsonb("request"),
  response: jsonb("response"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});
```

This one table gives us hit-rate per provider, cost per enriched row, and a
debugging trail for "why is this cell wrong" — which is otherwise the single
most frustrating thing about tools in this category.

Note `costCents` is `numeric(12,6)`, not an integer. Per-call costs are routinely
a fraction of a cent, and rounding them to whole cents makes the whole accounting
layer useless.

### Live updates by polling

While a run is active, the client polls:

```
GET /api/grid/tables/:id/changes?since=<version>
→ { rows: [...changed rows...], cursor: <max version>, activeJobs: 42 }
```

Poll every ~1.5s while `activeJobs > 0`, then stop. No websockets, no SSE, no
long-lived connections for a reverse proxy to buffer. The `version` column makes
this exact rather than approximate.

---

## 8. The grid UI

**[AG Grid Community](https://www.ag-grid.com/)** (`ag-grid-react` v36, MIT).

> **Correction, superseding an earlier draft of this document.** This section
> originally specified glide-data-grid, chosen from its GitHub page. That was
> wrong on the facts. The unscoped `glide-data-grid` package was **unpublished
> from npm on 2024-11-30**; the surviving `@glideapps/glide-data-grid@6.0.3` had
> its last real release around three years ago and declares
> `react: ^16.12.0 || 17.x || 18.x`, so it cannot be used on this app's React
> 19.2.4. The community fork `@platools/glide-data-grid` carries the same
> ceiling. Verify a package on npm, not on its README.

AG Grid Community is MIT, actively maintained, and explicitly supports React 19.
It provides virtual scrolling, inline editing, column resize and reorder, and
custom cell renderers. AG Grid v36 keeps range selection, clipboard and fill
handles in Enterprise modules, so this app implements those interactions in its
own grid layer while retaining the Community license.

Costs, accepted:

- **Bundle size** (~500KB+), by far the largest dependency in the app. Mitigated
  by loading the grid route dynamically so it never touches the outreach or CRM
  bundles.
- **Some features are Enterprise-licensed** (including the built-in range,
  clipboard and fill-handle modules, plus pivot, row grouping and
  master/detail). The current grid does not register those modules; adopting
  them later is a licensing decision to take deliberately rather than drift
  into.
- v33+ requires explicit module registration and uses the Theming API rather
  than imported CSS — a small amount of setup that differs from older examples.

Alternatives considered: **react-data-grid v7** is React-19-native and much
lighter, but is still `7.0.0-beta.61`, and a foundational component of a product
being open-sourced should not sit on a beta. **TanStack Table + Virtual** is the
most flexible and smallest, but headless — every piece of grid chrome
(selection, editing, resize, copy/paste) would be ours to build, which is real
Phase 1 time for control we do not yet need.

## 9. The seam: pushing into outreach and CRM

This is where the "single app" promise is actually cashed, and it is deliberately
a narrow, explicit interface rather than a shared data model.

A "Push to campaign" action maps grid columns onto `outreach_leads`:

- `email`, `firstName`, `lastName`, `company` → recognised columns
- **everything else → `customFields`**, keyed by column `key`

That last part is the reason this integration is nearly free.
`src/lib/outreach/scheduler.ts` already resolves leftover `{{key}}` tokens
against `customFields` case-insensitively, and `leadImport.ts` already
camelCases unknown CSV headers into it. Any enrichment column becomes a merge
field in a sequence with **no changes to the outreach sending path at all**.

The same shape applies to `crm_leads` later.

Deliberately excluded: making `outreach_leads` a view over `grid_rows`. It's the
cleaner long-term architecture, but it's a migration through the two most
business-critical, actively-running systems in the app, and there is no reason to
take that risk before the grid has proven itself.

---

## 10. Build phases

### Phase 0 — Open-source preparation (parallel, low effort)

The secrets audit is **already done and clean**: only `.env.example` is tracked,
`.env*` is gitignored, no env file appears anywhere in git history, and no
hardcoded credentials exist in `src/` or `scripts/`. Remaining:

- [ ] Add `LICENSE` (AGPL-3.0) — currently absent
- [ ] Rewrite `README.md` for a public audience: what it is, self-host quickstart
- [ ] Expand `.env.example` — it currently documents only `DATABASE_URL`, but the
      app reads `AUTH_PASSWORD`, `AUTH_SECRET`, `OUTREACH_TICK_SECRET` and more.
      A self-hoster cannot currently start this app from the example file alone.
- [ ] `docker-compose.yml` bundling app + Postgres for one-command self-host

### Phase 1 — Tables, grid, manual columns *(no execution at all)*

Schema, CRUD, glide-data-grid rendering JSONB rows, cell editing, add/reorder/
delete columns, CSV/XLSX import (`xlsx` is already a dependency).

Ship this before touching async execution. It is the foundation, it's where the
canvas learning curve lands, and it's independently useful as a list-builder.

### Phase 2 — Queue, DAG, HTTP runner

`grid_jobs`, `SKIP LOCKED` claiming, worker pool from `instrumentation.ts`,
topological sort with cycle rejection, polling endpoint, and the HTTP runner as
the first and only runner. Proves cascade, status, retry and backoff end-to-end
against one column type.

**Phases 1 and 2 carry essentially all the risk in this project.** Everything
after is adding runners to a working harness.

### Phase 3 — AI runner
Prompt templates, schema-constrained output, token-based cost capture.

### Phase 4 — Waterfall and cost accounting
`grid_cell_runs`, per-row caps, provider hit-rate reporting, and the first real
email-finder integrations.

### Phase 5 — Push to outreach and CRM
The mapping UI and write path described in §9.

### Phase 6 — Deferred
Formula runner, LinkedIn via Unipile (deferred at your call — LinkedIn outreach
already exists separately), saved views, filters, dedupe.

---

## 11. Risks and open questions

**Concurrency vs. the single-instance assumption.** The queue is multi-instance
safe; the outreach scheduler beside it is not. Anyone tempted to scale out must
fix `internalScheduler.ts` first. Worth a comment there pointing at this document.

**Canvas rendering effort.** The most likely source of Phase 1 schedule slip.
Budget real time for custom cell drawing.

**JSONB filtering at the top of the range.** Comfortable at 50k rows with
expression indexes. If tables start reaching several hundred thousand rows, revisit
§4 rather than trying to index around it.

**AGPL and your own use.** As copyright holder you're unaffected — you may run,
modify and even sell hosting without opening anything. The obligation falls on
third parties. Worth stating in the README, since AGPL scares off some users who
assume it restricts them more than it does.

**New tables need migration scripts.** Per `CLAUDE.md`, `scripts/` is the only
reproducible path to a fresh database. Every table here needs a matching
`scripts/*.ts` migration (new ones in TypeScript, run with `bun run`), guarded
with `IF NOT EXISTS`.

Open, and worth deciding before Phase 1 ends:

- Should the existing `domains` / `clean_domains` datasets be browsable as grid
  tables, or stay separate? They're a natural first data source.
- Does the CSV importer need to handle dedupe-on-import against existing rows,
  or is that a later column-level concern?
- One flat list of tables, or workbooks/folders as in the Clay screenshots?

---

## 12. Summary

Build it, borrowing three pieces: **glide-data-grid** (MIT) for the grid, a
**Postgres `SKIP LOCKED` queue** for execution, and the **Drizzle/Postgres setup
already here** for storage. No new services, so `docker run` + `DATABASE_URL`
remains the entire self-host story.

The architecture rests on one idea: this is a column DAG that fans out over rows,
not a spreadsheet. Hold that line — especially against the recurring temptation to
add a spreadsheet engine — and the rest follows.
