import "server-only";

import { sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { CLAIM_RETENTION_DAYS, ROLLOVER_JOB_PREFIX } from "./schedules";

/**
 * Slot claims in `scheduled_job_runs`. Whoever inserts the (job, slot) row
 * runs the slot; everyone else (another instance, an external cron call,
 * this process after a restart) sees it taken.
 *
 * A claim is also refused when the job has a run that STARTED at or after
 * the slot. For interval jobs that changes nothing; for the daily rollover
 * it means moving an organization's time zone or day start never rolls the
 * same day over twice (see dailyRollover.ts).
 *
 * If the table does not exist (an install that has not run
 * scripts/create-scheduled-job-runs.ts) every call answers "missing-table"
 * and one warning is logged per process: the scheduler then runs nothing,
 * and the endpoints run as they did before claims existed.
 */

export type ClaimResult = "claimed" | "taken" | "missing-table";

let warnedMissing = false;

function isMissingTable(error: unknown): boolean {
  for (let e = error as { code?: string; cause?: unknown } | undefined, depth = 0; e && depth < 5; e = e.cause as typeof e, depth++) {
    if (e.code === "42P01") return true;
  }
  return false;
}

function warnMissingTable() {
  if (warnedMissing) return;
  warnedMissing = true;
  console.error(
    "[scheduler] ======================================================================\n" +
      "[scheduler] Table scheduled_job_runs is missing: scheduled jobs will NOT run in-process,\n" +
      "[scheduler] and the job endpoints run without dedupe. Run the migration:\n" +
      "[scheduler]   bun scripts/create-scheduled-job-runs.ts\n" +
      "[scheduler] (Docker: docker compose exec app agentsdr-entrypoint bun scripts/create-scheduled-job-runs.ts)\n" +
      "[scheduler] ======================================================================",
  );
}

/** Claim `slot` of `job`. Never throws for a missing table; other database errors propagate. */
export async function claimSlot(job: string, slot: Date, now = new Date()): Promise<ClaimResult> {
  try {
    const rows = await db.execute<{ job: string }>(sql`
      insert into scheduled_job_runs (job, slot, started_at)
      select ${job}, ${slot.toISOString()}::timestamptz, ${now.toISOString()}::timestamptz
      where not exists (
        select 1 from scheduled_job_runs where job = ${job} and started_at >= ${slot.toISOString()}::timestamptz
      )
      on conflict (job, slot) do nothing
      returning job`);
    return rows.length > 0 ? "claimed" : "taken";
  } catch (error) {
    if (isMissingTable(error)) {
      warnMissingTable();
      return "missing-table";
    }
    throw error;
  }
}

/** Record how a claimed slot ended. Never throws: losing this line must not fail the job. */
export async function finishSlot(job: string, slot: Date, error: string | null): Promise<void> {
  try {
    await db.execute(sql`
      update scheduled_job_runs set finished_at = now(), error = ${error ? error.slice(0, 2000) : null}
      where job = ${job} and slot = ${slot.toISOString()}::timestamptz`);
  } catch (err) {
    console.error(`[scheduler] could not record the end of ${job} @ ${slot.toISOString()}:`, err);
  }
}

/**
 * When each job last started a run, for the given jobs (or every rollover
 * when `rollovers` is set). Null when the table is missing.
 */
export async function lastStarts(jobs: string[], rollovers = false): Promise<Map<string, Date> | null> {
  const named = jobs.length ? sql`job in (${sql.join(jobs.map((j) => sql`${j}`), sql`, `)})` : sql`false`;
  const rollover = rollovers ? sql`job like ${ROLLOVER_JOB_PREFIX + "%"}` : sql`false`;
  try {
    const rows = await db.execute<{ job: string; last: string | Date }>(sql`
      select job, max(started_at) as last from scheduled_job_runs
      where ${named} or ${rollover}
      group by job`);
    return new Map(rows.map((row) => [row.job, new Date(row.last)]));
  } catch (error) {
    if (isMissingTable(error)) {
      warnMissingTable();
      return null;
    }
    throw error;
  }
}

/** Delete claims older than CLAIM_RETENTION_DAYS. Returns how many, or null when the table is missing. */
export async function pruneClaims(): Promise<number | null> {
  try {
    const rows = await db.execute<{ job: string }>(sql`
      delete from scheduled_job_runs
      where slot < now() - make_interval(days => ${CLAIM_RETENTION_DAYS})
      returning job`);
    return rows.length;
  } catch (error) {
    if (isMissingTable(error)) {
      warnMissingTable();
      return null;
    }
    throw error;
  }
}
