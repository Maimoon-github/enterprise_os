import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { gridColumns, gridRows, type GridColumn } from "./schema";
import { inOrgTables } from "./scope";
import { runInOrganization } from "@/lib/tenancy/scope";
import { claim, type ClaimedJob, completeJob, deferJob, failJob, recoverStaleJobs, skipJob } from "./queue";
import { setCellMeta } from "./rows";
import { textColumnKeys } from "./formula-lookups";
import {
  allReferencedInputsEmpty,
  columnRunCondition,
  createSandbox,
  evaluateCondition,
  getRunner,
  PermanentRunError,
  type RunSession,
  type Sandbox,
} from "./runners";
import type { CellResult, CellValues, PendingCellResult } from "./types";
import { isMigrationControlPaused } from "@/lib/migration/controls";

/**
 * In-process worker pool draining grid_jobs.
 *
 * Deliberately the same deployment shape as outreach/internalScheduler.ts —
 * started from instrumentation.ts, no separate process, no Redis — so the
 * self-host story stays `docker run` plus DATABASE_URL. Unlike that scheduler
 * this one is safe under multiple instances, because claiming goes through
 * SKIP LOCKED (see queue.ts).
 */

const POLL_INTERVAL_MS = Number(process.env.GRID_WORKER_POLL_MS ?? 1000);
const CONCURRENCY = Number(process.env.GRID_WORKER_CONCURRENCY ?? 8);
const CELL_TIMEOUT_MS = Number(process.env.GRID_CELL_TIMEOUT_MS ?? 30_000);
const STALE_SWEEP_MS = 60_000;
// A drain ends after this long even with work left (the next tick resumes it),
// so the stale sweep still runs on a busy queue and sessions — which hold
// LOOKUP tables loaded at prepare() — never outlive a minute of edits.
const MAX_DRAIN_MS = 60_000;
const WORKER_STATE_KEY = Symbol.for("agentsdr.grid-worker-state");

type WorkerState = {
  owner: symbol;
  timer: ReturnType<typeof setInterval>;
};

type WorkerGlobal = typeof globalThis & {
  [WORKER_STATE_KEY]?: WorkerState;
};

let started = false;
let draining = false;
// A fresh token is created whenever this module is replaced by dev HMR. The
// new module clears the prior generation's timer before it begins polling.
const workerOwner = Symbol("grid-worker-generation");
// Sweep on the first pass as well as every minute thereafter (by the clock: a
// busy drain lasts up to MAX_DRAIN_MS, so counting drains would stretch it to
// an hour). This recovers rows left in `running` when a dev server or
// deployment was restarted.
let lastSweepAt = 0;

/**
 * Sessions live for one continuous drain, keyed by column.
 *
 * This is what makes formula columns viable: booting a QuickJS isolate and
 * loading lodash/moment/FormulaJS costs ~60ms against ~10µs per evaluation, so
 * one sandbox is shared by every row in the drain and disposed when it ends.
 *
 * The cache holds the in-flight prepare() PROMISE, not its result: jobs run
 * concurrently, and each of them would otherwise miss the cache before the
 * first prepare() resolved and build (and leak) a sandbox of its own. The key
 * includes the column's updated_at so an edit mid-drain gets a fresh session.
 */
type SessionCache = Map<string, Promise<RunSession>>;

function sessionFor(
  sessions: SessionCache,
  key: string,
  create: () => Promise<RunSession>,
): Promise<RunSession> {
  let session = sessions.get(key);
  if (!session) {
    session = create();
    sessions.set(key, session);
    // A failed prepare must not poison the rest of the drain.
    session.catch(() => {
      if (sessions.get(key) === session) sessions.delete(key);
    });
  }
  return session;
}

async function disposeSessions(sessions: SessionCache): Promise<void> {
  for (const pending of sessions.values()) {
    try {
      await (await pending).dispose?.();
    } catch {
      // A sandbox that fails to dispose must not stall the loop.
    }
  }
  sessions.clear();
}

function isPendingResult(result: CellResult | PendingCellResult): result is PendingCellResult {
  return "pending" in result && result.pending === true;
}

async function loadColumns(tableId: string): Promise<GridColumn[]> {
  return db
    .select()
    .from(gridColumns)
    .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.tableId, tableId)));
}

async function loadRow(tableId: string, rowId: string): Promise<CellValues | null> {
  const [row] = await db
    .select({ cells: gridRows.cells })
    .from(gridRows)
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), eq(gridRows.id, rowId)))
    .limit(1);
  return row?.cells ?? null;
}

async function runJob(job: ClaimedJob, sessions: SessionCache): Promise<void> {
  const columns = await loadColumns(job.tableId);
  const column = columns.find((c) => c.key === job.columnKey);

  if (!column) {
    // The column was deleted while the job sat in the queue. Not an error
    // worth surfacing on a cell that no longer exists.
    await failJob(job, "Column no longer exists", { permanent: true });
    return;
  }

  const runner = getRunner(column.type);
  if (!runner) {
    await failJob(job, `No runner for column type "${column.type}"`, { permanent: true });
    return;
  }

  const cells = await loadRow(job.tableId, job.rowId);
  if (!cells) {
    await failJob(job, "Row no longer exists", { permanent: true });
    return;
  }

  // "Only run if" is checked here, against the row as it stands now, so it
  // holds for every way a job gets queued. A false condition (or one that
  // cannot be evaluated) leaves the cell idle instead of spending a call. An
  // AI, HTTP or formula column whose referenced inputs all went blank since
  // queuing is skipped the same way.
  const condition = columnRunCondition(column);
  const skip = !job.providerState && (allReferencedInputsEmpty(column, cells)
    || (condition !== undefined && !(await conditionHolds(sessions, column, condition, cells))));
  if (skip) {
    await skipJob(job);
    return;
  }

  // Mark running so the grid shows progress mid-flight. Best-effort: losing
  // this update costs a spinner, whereas losing the terminal write in
  // completeJob() would strand the cell, which is why only that one is
  // transactional.
  await setCellMeta(job.rowId, job.columnKey, { status: "running" }).catch(() => {});

  try {
    const session = runner.prepare
      ? await sessionFor(sessions, `${column.id}:${column.updatedAt?.getTime() ?? 0}`, () =>
          runner.prepare!(column.config as never, {
            tableId: job.tableId,
            rowId: job.rowId,
            columnKey: job.columnKey,
            timeoutMs: CELL_TIMEOUT_MS,
          }),
        )
      : undefined;

    const result = await runner.run(
      column.config as never,
      cells,
      {
        tableId: job.tableId,
        rowId: job.rowId,
        columnKey: job.columnKey,
        timeoutMs: CELL_TIMEOUT_MS,
        providerState: job.providerState,
      },
      session,
    );

    if (isPendingResult(result)) {
      await deferJob(job, result);
      return;
    }

    // The cascade runs inside completeJob's transaction, from the row as the
    // database holds it NOW rather than the snapshot taken when this job
    // started: a sibling job finishing at the same moment has written its own
    // value since, and a dependent reading both would otherwise never be queued.
    await completeJob(job, result, { cascadeColumns: columns });
  } catch (err) {
    const permanent = err instanceof PermanentRunError;
    const message = err instanceof Error ? err.message : String(err);
    const audit = (err as { audit?: { provider?: string; request?: unknown; response?: unknown } }).audit;
    const { willRetry } = await failJob(job, message, { permanent, ...audit });
    if (!willRetry) {
      console.warn(`[grid/worker] ${job.columnKey} on row ${job.rowId} failed: ${message}`);
    }
    return;
  }
}

/** Evaluates a column's run condition in a sandbox shared across the drain. */
async function conditionHolds(
  sessions: SessionCache,
  column: GridColumn,
  condition: string,
  cells: CellValues,
): Promise<boolean> {
  try {
    const session = await sessionFor(sessions, `condition:${column.id}`, async () => {
      const [sandbox, textKeys] = await Promise.all([createSandbox(), textColumnKeys(column.tableId)]);
      return { sandbox, textKeys, dispose: () => sandbox.dispose() };
    });
    return await evaluateCondition(condition, cells, session.sandbox as Sandbox, session.textKeys as Set<string>);
  } catch {
    // A condition that cannot be evaluated must not authorise a paid call.
    return false;
  }
}
/**
 * One continuous drain: claim whenever there is a free slot, run, and keep
 * going until the queue has nothing ready and nothing is running.
 *
 * Refilling instead of claiming a batch and awaiting all of it means one slow
 * job (a 30 s provider call) no longer holds seven idle slots hostage until the
 * next tick. Sessions live for the whole drain and are disposed when it ends.
 */
async function drain(): Promise<void> {
  if (draining) return;
  if (isMigrationControlPaused("gridWorker")) return;
  draining = true;

  const workerGlobal = globalThis as WorkerGlobal;
  const sessions: SessionCache = new Map();
  const running = new Set<Promise<void>>();
  const startedAt = Date.now();
  try {
    if (startedAt - lastSweepAt >= STALE_SWEEP_MS) {
      lastSweepAt = startedAt;
      const n = await recoverStaleJobs();
      if (n) console.log(`[grid/worker] recovered ${n} stale job(s)`);
    }

    for (;;) {
      // Stop claiming when paused, or when dev HMR has handed the worker to a
      // newer module; what is already running finishes below.
      if (isMigrationControlPaused("gridWorker")) break;
      const state = workerGlobal[WORKER_STATE_KEY];
      if (state && state.owner !== workerOwner) break;
      if (Date.now() - startedAt > MAX_DRAIN_MS) break;

      const capacity = CONCURRENCY - running.size;
      const jobs = capacity > 0 ? await claim(capacity) : [];

      for (const job of jobs) {
        // Every job runs as the organization that owns its table.
        const task: Promise<void> = runInOrganization(job.organizationId, () => runJob(job, sessions))
          .catch((err) => {
            console.error("[grid/worker] job threw outside its handler:", err);
          })
          .finally(() => {
            running.delete(task);
          });
        running.add(task);
      }

      if (running.size === 0) break;
      // Nothing more is ready, or every slot is busy: wait for a job to finish
      // (its cascade may have queued more) before claiming again.
      if (!jobs.length || running.size >= CONCURRENCY) await Promise.race(running);
    }
  } catch (err) {
    console.error("[grid/worker] drain failed:", err);
  } finally {
    await Promise.allSettled([...running]);
    await disposeSessions(sessions);
    draining = false;
  }
}

/** Starts the loop. Idempotent — Next may call register() more than once. */
export function startGridWorker(): void {
  const workerGlobal = globalThis as WorkerGlobal;
  if (started && workerGlobal[WORKER_STATE_KEY]?.owner === workerOwner) return;
  started = true;

  const previous = workerGlobal[WORKER_STATE_KEY];
  if (previous && previous.owner !== workerOwner) clearInterval(previous.timer);

  console.log(
    `[grid/worker] starting — poll ${POLL_INTERVAL_MS}ms, concurrency ${CONCURRENCY}`,
  );

  const timer = setInterval(() => {
    // A replacement module may have taken ownership between timer ticks.
    if (workerGlobal[WORKER_STATE_KEY]?.owner !== workerOwner) {
      clearInterval(timer);
      return;
    }
    void drain();
  }, POLL_INTERVAL_MS);
  workerGlobal[WORKER_STATE_KEY] = { owner: workerOwner, timer };

  void drain();
}

/** Runs one pass synchronously. Used by tests and the manual-run endpoint. */
export async function drainOnce(): Promise<void> {
  await drain();
}
