import { and, asc, desc, eq, inArray, lte, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { gridCellRuns, gridColumns, gridJobs, gridRows, gridTables, type GridColumn, type GridJob } from "./schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import { inOrgTables } from "./scope";
import type { CellResult, CellValues, PendingCellResult } from "./types";
import { cascadeTargets, type RowChange } from "./cascade-targets";
import { cleanJson, cleanString } from "./sanitize";

/**
 * The work queue for cell execution — see docs/design/enrichment-plan.md §5.
 *
 * Jobs are claimed with FOR UPDATE SKIP LOCKED, which gives this the
 * distributed lock that outreach/internalScheduler.ts documents itself as
 * lacking: two workers, or two instances, cannot claim the same job. The
 * outreach tick beside it would still double-send if scaled out; this will not.
 */

/** A claim older than this is treated as a worker that died mid-run. */
const STALE_LOCK_MS = 5 * 60 * 1000;

/** `delaySeconds` holds the job back from the claimer — the column's "Delay" setting. */
export type EnqueueTarget = { rowId: string; columnKey: string; delaySeconds?: number };

/** A claimed job plus the organization of its table — what the worker scopes each run to. */
export type ClaimedJob = GridJob & { organizationId: string };

type Tx = Parameters<Parameters<typeof db.transaction>[0]>[0];

/**
 * Queues cells, skipping any already running or waiting on a provider.
 *
 * The (row_id, column_key) unique constraint makes this an upsert: re-running
 * a cell moves its existing job back to queued rather than stacking a second
 * one, so a user hammering "Run" cannot flood the queue.
 *
 * The jobs and the cells' "queued" metadata commit together, and only for the
 * jobs this call actually queued. Writing the metadata after the jobs were
 * visible let a fast worker finish a cell first, and the late "queued" then
 * overwrote its result forever; in one transaction a worker cannot claim a job
 * before its marker exists, and every terminal write lands after it. Pass `tx`
 * to queue inside a caller's transaction (the worker's cascade does, so a
 * finished job and the jobs it queues become visible at one instant).
 */
export async function enqueue(
  tableId: string,
  targets: EnqueueTarget[],
  opts: { priority?: number; tx?: Tx } = {},
): Promise<number> {
  if (!targets.length) return 0;
  // Fail closed: a table id from another organization queues nothing. Inside a
  // caller's transaction the check runs on it — a second connection per
  // in-flight job would exhaust the pool.
  const reader = opts.tx ?? db;
  const [table] = await reader
    .select({ id: gridTables.id })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.id, tableId)))
    .limit(1);
  if (!table) throw new Error("That table no longer exists");

  const CHUNK = 500;
  let queued = 0;

  for (let i = 0; i < targets.length; i += CHUNK) {
    const chunk = targets.slice(i, i + CHUNK);
    const write = async (tx: Tx) => {
      const inserted = await tx
        .insert(gridJobs)
        .values(
          chunk.map((t) => ({
            tableId,
            rowId: t.rowId,
            columnKey: t.columnKey,
            status: "queued" as const,
            priority: opts.priority ?? 0,
            attempts: 0,
            runAfter: new Date(Date.now() + (t.delaySeconds ?? 0) * 1000),
          })),
        )
        .onConflictDoUpdate({
          target: [gridJobs.rowId, gridJobs.columnKey],
          set: {
            status: "queued",
            attempts: 0,
            error: null,
            providerState: null,
            lockedAt: null,
            runAfter: sql`excluded.run_after`,
            updatedAt: new Date(),
          },
          // Leave a job that is mid-flight alone; re-queuing it under the worker
          // would orphan the run in progress.
          where: sql`${gridJobs.status} NOT IN ('running', 'waiting')`,
        })
        .returning({ rowId: gridJobs.rowId, columnKey: gridJobs.columnKey });

      // Mark exactly the cells that were queued so the grid shows pending state
      // without waiting for a worker to pick the job up.
      await markQueued(tx, tableId, inserted);
      return inserted.length;
    };
    queued += opts.tx ? await write(opts.tx) : await db.transaction(write);
  }

  return queued;
}

async function markQueued(tx: Tx, tableId: string, targets: { rowId: string; columnKey: string }[]): Promise<void> {
  const byColumn = new Map<string, Set<string>>();
  for (const t of targets) {
    const rowIds = byColumn.get(t.columnKey) ?? new Set<string>();
    rowIds.add(t.rowId);
    byColumn.set(t.columnKey, rowIds);
  }

  const CHUNK = 500;
  for (const [columnKey, ids] of byColumn) {
    const rowIds = [...ids];
    const patch = JSON.stringify({ [columnKey]: { status: "queued" } });
    for (let i = 0; i < rowIds.length; i += CHUNK) {
      await tx
        .update(gridRows)
        .set({
          cellMeta: sql`${gridRows.cellMeta} || ${patch}::jsonb`,
          version: sql`nextval('grid_row_version_seq')`,
          updatedAt: new Date(),
        })
        .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), inArray(gridRows.id, rowIds.slice(i, i + CHUNK))));
    }
  }
}

/**
 * Claims up to `limit` runnable jobs.
 *
 * SKIP LOCKED is what makes this safe to call concurrently: rows locked by
 * another claimer are passed over instead of blocking, so N workers drain the
 * queue in parallel without ever colliding on the same job.
 *
 * Done as a typed SELECT ... FOR UPDATE SKIP LOCKED followed by an UPDATE in
 * the same transaction, rather than one raw `UPDATE ... RETURNING *`. The raw
 * form works in SQL but bypasses drizzle's column mapping, so postgres-js
 * hands back snake_case keys and every `job.tableId` reads as undefined. The
 * locks are held until the transaction commits, so the two statements are just
 * as atomic as the single one was.
 *
 * Deliberately global: it runs in the worker loop with no organization scope,
 * claiming across every organization. Each claimed job carries the
 * organization of its table, and the worker runs it inside that scope.
 */
export async function claim(limit: number): Promise<ClaimedJob[]> {
  return db.transaction(async (tx) => {
    const locked = await tx
      .select({ id: gridJobs.id })
      .from(gridJobs)
      .where(and(inArray(gridJobs.status, ["queued", "waiting"]), lte(gridJobs.runAfter, new Date())))
      .orderBy(desc(gridJobs.priority), asc(gridJobs.createdAt))
      .limit(limit)
      .for("update", { skipLocked: true });

    if (!locked.length) return [];

    const claimed = await tx
      .update(gridJobs)
      .set({
        status: "running",
        lockedAt: new Date(),
        attempts: sql`CASE WHEN ${gridJobs.status} = 'queued' THEN ${gridJobs.attempts} + 1 ELSE ${gridJobs.attempts} END`,
        updatedAt: new Date(),
      })
      .where(
        inArray(
          gridJobs.id,
          locked.map((l) => l.id),
        ),
      )
      .returning();

    const tables = await tx
      .select({ id: gridTables.id, organizationId: gridTables.organizationId })
      .from(gridTables)
      .where(inArray(gridTables.id, [...new Set(claimed.map((job) => job.tableId))]));
    const organizationByTable = new Map(tables.map((table) => [table.id, table.organizationId]));
    // A job whose table is gone cannot be attributed to an organization; the
    // cascade makes that impossible, but never run one unscoped.
    return claimed.flatMap((job) => {
      const organizationId = organizationByTable.get(job.tableId);
      return organizationId ? [{ ...job, organizationId }] : [];
    });
  });
}

/** Returns jobs whose worker died mid-run to the queue. Global, like claim(): it touches no payload. */
export async function recoverStaleJobs(): Promise<number> {
  const recovered = await db
    .update(gridJobs)
    .set({
      status: sql`CASE WHEN ${gridJobs.providerState} IS NULL THEN 'queued' ELSE 'waiting' END`,
      lockedAt: null,
      updatedAt: new Date(),
    })
    .where(
      and(
        eq(gridJobs.status, "running"),
        sql`${gridJobs.lockedAt} < now() - ${`${STALE_LOCK_MS} milliseconds`}::interval`,
      ),
    )
    .returning({ id: gridJobs.id });
  return recovered.length;
}

/** Releases an accepted asynchronous provider task until its next poll. */
export async function deferJob(job: GridJob, result: PendingCellResult): Promise<void> {
  await db.transaction(async (tx) => {
    await tx
      .update(gridJobs)
      .set({
        status: "waiting",
        providerState: result.state,
        lockedAt: null,
        runAfter: new Date(Date.now() + Math.max(1_000, result.pollAfterMs)),
        error: null,
        updatedAt: new Date(),
      })
      .where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.id, job.id)));
    await tx
      .update(gridRows)
      .set({
        cellMeta: sql`${gridRows.cellMeta} || ${JSON.stringify({ [job.columnKey]: { status: "processing" } })}::jsonb`,
        version: sql`nextval('grid_row_version_seq')`,
        updatedAt: new Date(),
      })
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, job.tableId), eq(gridRows.id, job.rowId)));
  });
}

/**
 * Records a successful run: the value, its metadata, and an audit row.
 *
 * The value and metadata are written in one statement so a reader can never
 * observe a cell whose value has landed but which still claims to be running.
 */
export async function completeJob(
  job: GridJob,
  result: CellResult,
  opts: { cascadeColumns?: GridColumn[] } = {},
): Promise<void> {
  const meta = {
    status: "success" as const,
    // A provider/AI/HTTP call that found nothing is still a finished run; the
    // grid tells "no result" from "never ran" by this.
    ...(result.outcome === "hit" || result.outcome === "miss" ? { outcome: result.outcome } : {}),
    provider: result.provider,
    costCents: result.costCents,
    runAt: new Date().toISOString(),
  };
  const produced = cleanJson({ [job.columnKey]: result.value ?? null, ...(result.outputs ?? {}) });

  await db.transaction(async (tx) => {
    // Job first, then the row — the order every other writer here uses, so a
    // concurrent enqueue (job, then row) can never deadlock against this.
    await tx.delete(gridJobs).where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.id, job.id)));

    // Only keys that are still columns: an output column deleted while the job
    // ran would otherwise keep receiving values no one can see.
    const current = await tx
      .select({ key: gridColumns.key })
      .from(gridColumns)
      .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.tableId, job.tableId)));
    const live = new Set(current.map((column) => column.key));
    const values = Object.fromEntries(Object.entries(produced).filter(([key]) => live.has(key)));
    const metadata = Object.fromEntries(Object.keys(values).map((key) => [key, meta]));

    if (Object.keys(values).length) {
      await tx
        .update(gridRows)
        .set({
          cells: sql`${gridRows.cells} || ${JSON.stringify(values)}::jsonb`,
          cellMeta: sql`${gridRows.cellMeta} || ${JSON.stringify(metadata)}::jsonb`,
          version: sql`nextval('grid_row_version_seq')`,
          updatedAt: new Date(),
        })
        .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, job.tableId), eq(gridRows.id, job.rowId)));
    }

    await recordRun(tx, {
      tableId: job.tableId,
      rowId: job.rowId,
      columnKey: job.columnKey,
      provider: result.provider ?? null,
      outcome: result.outcome,
      costCents: String(result.costCents ?? 0),
      latencyMs: result.latencyMs ?? null,
      request: result.request ?? null,
      response: result.response ?? null,
    });

    // Queue the dependents in the same transaction: the finished job and the
    // jobs it triggers appear at one instant, so the table's active-job count
    // never dips to zero between them and a polling client keeps polling.
    // Nothing here may fail the completion, hence the savepoint.
    if (opts.cascadeColumns) {
      try {
        await tx.transaction(async (savepoint) => {
          const [fresh] = await savepoint
            .select({ cells: gridRows.cells })
            .from(gridRows)
            .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, job.tableId), eq(gridRows.id, job.rowId)))
            .limit(1);
          if (!fresh) return;
          await cascadeRows(
            job.tableId,
            [{ rowId: job.rowId, cells: fresh.cells ?? {}, changedKeys: Object.keys(values) }],
            opts.cascadeColumns!,
            { tx: savepoint },
          );
        });
      } catch (err) {
        console.error(`[grid/queue] cascade after ${job.columnKey} on row ${job.rowId} failed:`, err);
      }
    }
  });
}

/**
 * Appends the audit row inside a savepoint. The row may have been deleted
 * while the job ran, which makes the foreign key reject the insert; losing an
 * audit line must not abort the completion or failure it describes.
 */
async function recordRun(
  tx: Tx,
  run: Omit<typeof gridCellRuns.$inferInsert, "request" | "response"> & { request: unknown; response: unknown },
): Promise<void> {
  try {
    await tx.transaction(async (savepoint) => {
      await savepoint.insert(gridCellRuns).values({
        ...run,
        request: cleanJson(run.request) as never,
        response: cleanJson(run.response) as never,
      });
    });
  } catch (err) {
    console.warn("[grid/queue] could not record the run:", err instanceof Error ? err.message : err);
  }
}

/**
 * Drops a job without running it and returns its cell to idle — used when the
 * column's "Only run if" is false or every input went blank after queuing.
 */
export async function skipJob(job: GridJob): Promise<void> {
  await db.transaction(async (tx) => {
    await tx.delete(gridJobs).where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.id, job.id)));
    await tx
      .update(gridRows)
      .set({
        cellMeta: sql`${gridRows.cellMeta} - ${job.columnKey}::text`,
        version: sql`nextval('grid_row_version_seq')`,
        updatedAt: new Date(),
      })
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, job.tableId), eq(gridRows.id, job.rowId)));
  });
}

/**
 * Records a failure.
 *
 * `permanent` failures — a broken formula, a 4xx, a missing env var — are not
 * retried: they will fail identically next time, and retrying them three times
 * only delays the queue and triples the spend on anything that did charge.
 */
export async function failJob(
  job: GridJob,
  error: string,
  opts: { permanent?: boolean; costCents?: number; provider?: string; request?: unknown; response?: unknown } = {},
): Promise<{ willRetry: boolean }> {
  error = cleanString(error);
  const providerState = job.providerState ?? null;
  const pollErrors = providerState ? Number(providerState.pollErrors ?? 0) + 1 : 0;
  const exhausted = providerState ? pollErrors >= job.maxAttempts : job.attempts >= job.maxAttempts;
  const willRetry = !opts.permanent && !exhausted;

  // Exponential backoff: 2s, 8s, 32s.
  const failureCount = providerState ? pollErrors : job.attempts;
  const delayMs = 2000 * Math.pow(4, Math.max(0, failureCount - 1));

  await db.transaction(async (tx) => {
    if (willRetry) {
      await tx
        .update(gridJobs)
        .set({
          status: job.providerState ? "waiting" : "queued",
          providerState: providerState ? { ...providerState, pollErrors } : null,
          lockedAt: null,
          error,
          runAfter: new Date(Date.now() + delayMs),
          updatedAt: new Date(),
        })
        .where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.id, job.id)));
      if (providerState) {
        await tx
          .update(gridRows)
          .set({
            cellMeta: sql`${gridRows.cellMeta} || ${JSON.stringify({ [job.columnKey]: { status: "processing" } })}::jsonb`,
            version: sql`nextval('grid_row_version_seq')`,
            updatedAt: new Date(),
          })
          .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, job.tableId), eq(gridRows.id, job.rowId)));
      }
    } else {
      await tx.delete(gridJobs).where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.id, job.id)));
    }

    // Only surface the error on the cell once it is final; a cell blinking to
    // "error" between retries reads as a failure that has not happened yet.
    if (!willRetry) {
      const meta = { status: "error" as const, error, runAt: new Date().toISOString() };
      await tx
        .update(gridRows)
        .set({
          cellMeta: sql`${gridRows.cellMeta} || ${JSON.stringify({ [job.columnKey]: meta })}::jsonb`,
          version: sql`nextval('grid_row_version_seq')`,
          updatedAt: new Date(),
        })
        .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, job.tableId), eq(gridRows.id, job.rowId)));
    }

    await recordRun(tx, {
      tableId: job.tableId,
      rowId: job.rowId,
      columnKey: job.columnKey,
      provider: opts.provider ?? null,
      outcome: "error",
      costCents: String(opts.costCents ?? 0),
      request: opts.request ?? null,
      response: opts.response ?? { error },
    });
  });

  return { willRetry };
}

/**
 * Queues the columns that read the changed keys, for the given rows.
 *
 * This cascade is what the table's "Auto-run" toggle controls (the readiness
 * rules live in cascade-targets.ts). It takes many rows so a 1,000-row paste
 * is one table lookup and one batched enqueue, not a round trip per row.
 */
export async function cascadeRows(
  tableId: string,
  changes: RowChange[],
  columns: GridColumn[],
  opts: { tx?: Tx; priority?: number } = {},
): Promise<number> {
  if (!changes.length || !columns.some((c) => c.autoRun && c.dependsOn.length)) return 0;

  // The table-level Auto-run switch sits above each column's own.
  const [table] = await (opts.tx ?? db)
    .select({ autoRun: gridTables.autoRun })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.id, tableId)))
    .limit(1);
  if (!table?.autoRun) return 0;

  const targets = cascadeTargets(columns, changes);
  if (!targets.length) return 0;
  return enqueue(tableId, targets, opts);
}

/** Single-row form of cascadeRows. */
export async function cascade(
  tableId: string,
  rowId: string,
  columnKey: string,
  columns: GridColumn[],
  cells: CellValues,
): Promise<number> {
  return cascadeRows(tableId, [{ rowId, cells, changedKeys: [columnKey] }], columns);
}

/** Queued + running jobs for a table, for the toolbar counter. */
export async function activeJobCount(tableId: string): Promise<number> {
  const [row] = await db
    .select({ n: sql<number>`count(*)::int` })
    .from(gridJobs)
    .where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.tableId, tableId), inArray(gridJobs.status, ["queued", "running", "waiting"])));
  return row?.n ?? 0;
}

/** Statuses that claim a job is on its way; with no job behind them they are stale. */
const IN_FLIGHT_STATUSES = ["queued", "running", "processing"] as const;

/**
 * Clears cells that claim to be queued, running or processing but have no job
 * left — the grid would spin on them forever. Returns how many cells it reset.
 *
 * Bounded to `limit` rows per call; the next call takes the rest. The cell and
 * its job are always written in one transaction, so a cell with no job cannot
 * be one that is mid-write.
 */
export async function reconcileStuckCells(tableId: string, limit = 1000): Promise<number> {
  const rows = await db.execute<{ keys: string[] }>(sql`
    WITH stale AS (
      SELECT r.id, array_agg(e.key) AS keys
      FROM ${gridRows} r
      CROSS JOIN LATERAL jsonb_each(r.cell_meta) AS e(key, value)
      WHERE r.table_id = ${tableId}::uuid
        AND r.table_id IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})
        AND jsonb_typeof(e.value) = 'object'
        AND e.value->>'status' IN (${sql.join(IN_FLIGHT_STATUSES.map((status) => sql`${status}`), sql`, `)})
        AND NOT EXISTS (
          SELECT 1 FROM ${gridJobs} j
          WHERE j.row_id = r.id AND j.column_key = e.key AND j.table_id = r.table_id
        )
      GROUP BY r.id
      LIMIT ${limit}
    )
    UPDATE ${gridRows} AS target
    SET cell_meta = target.cell_meta - stale.keys,
        version = nextval('grid_row_version_seq'),
        updated_at = now()
    FROM stale
    WHERE target.id = stale.id
    RETURNING stale.keys AS keys
  `);
  return rows.reduce((sum, row) => sum + row.keys.length, 0);
}

// One sweep per table per interval and process: the changes poll calls it each
// time a table is idle, and it scans the table's metadata.
const RECONCILE_EVERY_MS = 10_000;
const lastReconcile = new Map<string, number>();

/** reconcileStuckCells for the idle poll: throttled, and never fails the poll. */
export async function reconcileIdleTable(tableId: string): Promise<number> {
  const now = Date.now();
  if (now - (lastReconcile.get(tableId) ?? 0) < RECONCILE_EVERY_MS) return 0;
  lastReconcile.set(tableId, now);
  if (lastReconcile.size > 500) lastReconcile.delete(lastReconcile.keys().next().value as string);
  try {
    return await reconcileStuckCells(tableId);
  } catch (err) {
    console.warn("[grid/queue] reconcile failed:", err instanceof Error ? err.message : err);
    return 0;
  }
}

/**
 * Drops every pending job for a table — the "Stop" button.
 *
 * The cells those jobs had marked queued or processing go back to idle in the
 * same transaction; otherwise the grid would spin on them forever. Cells that
 * claim to be in flight with no job at all (left by an earlier race or a crash)
 * are reset too. Returns how many cells were reset.
 */
export async function cancelTableJobs(tableId: string): Promise<number> {
  const reset = await db.transaction(async (tx) => {
    const deleted = await tx
      .delete(gridJobs)
      .where(and(inOrgTables(gridJobs.tableId), eq(gridJobs.tableId, tableId), inArray(gridJobs.status, ["queued", "waiting"])))
      .returning({ rowId: gridJobs.rowId, columnKey: gridJobs.columnKey });

    const keysByRow = new Map<string, string[]>();
    for (const { rowId, columnKey } of deleted) {
      keysByRow.set(rowId, [...(keysByRow.get(rowId) ?? []), columnKey]);
    }

    const CHUNK = 250;
    const rows = [...keysByRow.entries()];
    for (let i = 0; i < rows.length; i += CHUNK) {
      const values = sql.join(
        rows
          .slice(i, i + CHUNK)
          .map(([rowId, keys]) => sql`(${rowId}::uuid, ARRAY[${sql.join(keys.map((key) => sql`${key}`), sql`, `)}]::text[])`),
        sql`, `,
      );
      await tx.execute(sql`
        UPDATE ${gridRows}
        SET cell_meta = ${gridRows.cellMeta} - source.keys,
            version = nextval('grid_row_version_seq'),
            updated_at = now()
        FROM (VALUES ${values}) AS source(id, keys)
        WHERE ${gridRows.id} = source.id
          AND ${gridRows.tableId} = ${tableId}::uuid
          AND ${gridRows.tableId} IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})
      `);
    }
    return deleted.length;
  });
  return reset + (await reconcileStuckCells(tableId));
}
