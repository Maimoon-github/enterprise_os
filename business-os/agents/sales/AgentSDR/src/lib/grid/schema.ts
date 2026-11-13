import {
  pgTable,
  type AnyPgColumn,
  uuid,
  text,
  integer,
  bigint,
  boolean,
  jsonb,
  numeric,
  timestamp,
  doublePrecision,
  unique,
  index, uniqueIndex } from "drizzle-orm/pg-core";
import type {
  CellMetaMap,
  CellValues,
  ColumnConfig,
  ColumnType,
  JobStatus,
  RunOutcome,
  TableView,
} from "./types";
import { organizations } from "@/lib/auth/schema";

/**
 * Enrichment grid — the Clay-style layer. See docs/design/enrichment-plan.md for the
 * reasoning behind this shape; the short version is that user data lives in a
 * JSONB blob per row rather than in physical Postgres columns, because
 * creating columns at runtime would mean runtime DDL, which this repo's
 * migration convention (scripts/ as hand-written history) does not allow.
 *
 * Created by scripts/create-grid-tables.ts. Remember to keep the table names
 * in sync with OWNED_TABLES in drizzle.config.ts.
 */

/**
 * A folder on the All Files screen. Folders nest through `parentId`; a NULL
 * parent means the folder sits at the root.
 */
export const gridFolders = pgTable(
  "grid_folders",
  {
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id),
    id: uuid("id").primaryKey().defaultRandom(),
    name: text("name").notNull(),
    /** NULL = root level. Deleting a folder cascades to its subfolders. */
    parentId: uuid("parent_id").references((): AnyPgColumn => gridFolders.id, {
      onDelete: "cascade",
    }),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
  },
  (t) => [index("grid_folders_organization_idx").on(t.organizationId), index("grid_folders_parent_idx").on(t.parentId)],
);

/**
 * A workbook holds several tables, shown as sheet tabs along the bottom of the
 * grid. Deleting one cascades to its tables and everything under them.
 */
export const gridWorkbooks = pgTable(
  "grid_workbooks",
  {
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id),
    id: uuid("id").primaryKey().defaultRandom(),
    name: text("name").notNull(),
    description: text("description"),
    /**
     * NULL = the root of All Files. Deliberately SET NULL rather than CASCADE
     * on folder delete: dropping a folder must not take the user's tables with
     * it, so its workbooks resurface at the root instead.
     */
    folderId: uuid("folder_id").references(() => gridFolders.id, { onDelete: "set null" }),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
  },
  (t) => [index("grid_workbooks_organization_idx").on(t.organizationId), index("grid_workbooks_folder_idx").on(t.folderId)],
);

/** One user-created table (a "sheet"). Rows and columns hang off this. */
export const gridTables = pgTable("grid_tables", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  workbookId: uuid("workbook_id")
    .notNull()
    .references(() => gridWorkbooks.id, { onDelete: "cascade" }),
  name: text("name").notNull(),
  /** Sheet-tab order. Fractional, so a drag rewrites one row. */
  position: doublePrecision("position").notNull(),
  description: text("description"),
  /** Master switch behind the "Auto-run" toggle — gates the whole cascade. */
  autoRun: boolean("auto_run").notNull().default(true),
  /** Saved view: hidden columns, filters and sorts. Read by "Default view". */
  view: jsonb("view").$type<TableView>().notNull().default({}),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
},
  (t) => [index("grid_tables_organization_idx").on(t.organizationId)],
);

/**
 * One user-defined column.
 *
 * `key` vs `name` matters: the JSONB in grid_rows.cells is keyed by `key`,
 * which is generated once and never changes. `name` is the display label and
 * is freely renameable. Without that split, renaming a column would mean
 * rewriting every row's JSONB.
 */
export const gridColumns = pgTable(
  "grid_columns",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tableId: uuid("table_id")
      .notNull()
      .references(() => gridTables.id, { onDelete: "cascade" }),
    /** Stable JSONB key. Generated once, NEVER renamed. */
    key: text("key").notNull(),
    /** Display label. Cosmetic, user-renameable. */
    name: text("name").notNull(),
    type: text("type").notNull().$type<ColumnType>(),
    config: jsonb("config").$type<ColumnConfig>().notNull().default({}),
    /**
     * Column keys this one reads — the DAG edges. Derived from `config` by the
     * runner's resolveDeps(), never set by hand. Cycles are rejected on save.
     */
    dependsOn: text("depends_on").array().notNull().default([]),
    /** Fractional index, so inserting between two columns touches one row. */
    position: doublePrecision("position").notNull(),
    autoRun: boolean("auto_run").notNull().default(true),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
  },
  (t) => [
    unique("grid_columns_table_key_uq").on(t.tableId, t.key),
    index("grid_columns_table_pos_idx").on(t.tableId, t.position),
  ],
);

/**
 * One row. All user data lives in `cells`.
 *
 * `version` is drawn from a single global sequence (grid_row_version_seq), not
 * incremented per row. That is deliberate: a per-row counter is not comparable
 * across rows, so `WHERE version > :cursor` — which is how the client polls for
 * changes — would be meaningless. One shared sequence makes every write
 * globally ordered, so the cursor is exact. Timestamps were rejected for the
 * same job because of ties and clock skew at sub-second job completion.
 */
export const gridRows = pgTable(
  "grid_rows",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tableId: uuid("table_id")
      .notNull()
      .references(() => gridTables.id, { onDelete: "cascade" }),
    /** Fractional index — reorder/insert without renumbering neighbours. */
    position: doublePrecision("position").notNull(),
    /** The value plane: { [columnKey]: value }. */
    cells: jsonb("cells").$type<CellValues>().notNull().default({}),
    /** The metadata plane: { [columnKey]: CellMeta }. */
    cellMeta: jsonb("cell_meta").$type<CellMetaMap>().notNull().default({}),
    /** Global monotonic write marker — the polling cursor. See above. */
    version: bigint("version", { mode: "number" }).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
  },
  (t) => [
    index("grid_rows_table_pos_idx").on(t.tableId, t.position),
    index("grid_rows_table_version_idx").on(t.tableId, t.version),
  ],
);

/**
 * The work queue. One job per (row, column) cell.
 *
 * Claimed with FOR UPDATE SKIP LOCKED, which gives this the distributed lock
 * that src/lib/outreach/internalScheduler.ts documents itself as lacking — so
 * unlike the outreach tick, this survives running more than one instance.
 *
 * The unique constraint on (row_id, column_key) means a cell can be queued
 * only once; re-running updates the existing job instead of stacking copies.
 */
export const gridJobs = pgTable(
  "grid_jobs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tableId: uuid("table_id")
      .notNull()
      .references(() => gridTables.id, { onDelete: "cascade" }),
    rowId: uuid("row_id")
      .notNull()
      .references(() => gridRows.id, { onDelete: "cascade" }),
    columnKey: text("column_key").notNull(),
    status: text("status").notNull().default("queued").$type<JobStatus>(),
    priority: integer("priority").notNull().default(0),
    attempts: integer("attempts").notNull().default(0),
    maxAttempts: integer("max_attempts").notNull().default(3),
    /** Backoff target — a job is invisible to the claimer until now() passes. */
    runAfter: timestamp("run_after", { withTimezone: true }).defaultNow(),
    /** Set on claim; a stale value means the worker died mid-run. */
    lockedAt: timestamp("locked_at", { withTimezone: true }),
    /** Opaque provider continuation data, such as Snov.io's task_hash. */
    providerState: jsonb("provider_state").$type<Record<string, unknown>>(),
    error: text("error"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
  },
  (t) => [
    unique("grid_jobs_cell_uq").on(t.rowId, t.columnKey),
    index("grid_jobs_claim_idx").on(t.status, t.runAfter),
    index("grid_jobs_table_status_idx").on(t.tableId, t.status),
  ],
);

/**
 * Append-only audit of every provider attempt, including misses — which are
 * billed too, and are the whole reason waterfall ordering can be tuned.
 *
 * This is also the answer to "why is this cell wrong", which is otherwise the
 * most frustrating thing about tools in this category.
 */
export const gridCellRuns = pgTable(
  "grid_cell_runs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tableId: uuid("table_id")
      .notNull()
      .references(() => gridTables.id, { onDelete: "cascade" }),
    rowId: uuid("row_id")
      .notNull()
      .references(() => gridRows.id, { onDelete: "cascade" }),
    columnKey: text("column_key").notNull(),
    provider: text("provider"),
    outcome: text("outcome").notNull().$type<RunOutcome>(),
    /**
     * numeric, not integer: per-call costs are routinely a fraction of a cent,
     * and rounding them to whole cents makes the accounting layer useless.
     */
    costCents: numeric("cost_cents", { precision: 12, scale: 6 }).notNull().default("0"),
    latencyMs: integer("latency_ms"),
    request: jsonb("request"),
    response: jsonb("response"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  },
  (t) => [
    index("grid_cell_runs_cell_idx").on(t.rowId, t.columnKey),
    index("grid_cell_runs_table_created_idx").on(t.tableId, t.createdAt),
  ],
);

/**
 * Registered enrichment providers.
 *
 * Each row is a connected integration account with its own UUID. User-entered
 * Credentials live in the one-to-one grid_provider_credentials table below.
 * `authEnvVar` remains only so old rows can be shown as needing reconnection;
 * integration actions never read credentials from it.
 */
export const gridProviders = pgTable("grid_providers", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  key: text("key").notNull(),
  name: text("name").notNull(),
  baseUrl: text("base_url"),
  /** Deprecated. Integration actions never resolve credentials from this field. */
  authEnvVar: text("auth_env_var"),
  /** Fallback per-call cost when the provider doesn't report one. */
  defaultCostCents: numeric("default_cost_cents", { precision: 12, scale: 6 })
    .notNull()
    .default("0"),
  /** Feeds the per-provider semaphore in the worker pool. */
  rateLimitPerMin: integer("rate_limit_per_min"),
  config: jsonb("config").$type<Record<string, unknown>>().notNull().default({}),
  enabled: boolean("enabled").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
},
  (t) => [
    index("grid_providers_organization_idx").on(t.organizationId),
    uniqueIndex("grid_providers_org_key_uq").on(t.organizationId, t.key),
  ],
);

/**
 * Secret material for one connected integration account.
 *
 * The entire credential object is encrypted as one authenticated AES-GCM
 * payload. That keeps this schema stable whether an integration needs one API
 * key or several fields such as clientId/clientSecret. Plaintext is produced
 * only by the server immediately before an integration call.
 */
export const gridProviderCredentials = pgTable("grid_provider_credentials", {
  id: uuid("id").primaryKey().defaultRandom(),
  providerId: uuid("provider_id")
    .notNull()
    .unique()
    .references(() => gridProviders.id, { onDelete: "cascade" }),
  encryptedPayload: text("encrypted_payload").notNull(),
  encryptionVersion: text("encryption_version").notNull().default("v1"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
});

export type GridFolder = typeof gridFolders.$inferSelect;
export type GridWorkbook = typeof gridWorkbooks.$inferSelect;
export type GridTable = typeof gridTables.$inferSelect;
export type GridColumn = typeof gridColumns.$inferSelect;
export type GridRow = typeof gridRows.$inferSelect;
export type GridJob = typeof gridJobs.$inferSelect;
export type GridCellRun = typeof gridCellRuns.$inferSelect;
export type GridProvider = typeof gridProviders.$inferSelect;
export type GridProviderCredential = typeof gridProviderCredentials.$inferSelect;
