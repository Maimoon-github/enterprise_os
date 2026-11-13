import { AsyncLocalStorage } from "node:async_hooks";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { jobRuns, jobLogs } from "./schema";
import { serializeError } from "./serializeError";

/**
 * console.log/warn/error made inside a tracked job are also persisted as
 * JobLog rows of that job's run — no changes needed in the job functions.
 *
 * The run a line belongs to is found through AsyncLocalStorage, not by
 * swapping the console in and out per job: with several jobs running at once
 * (the scheduler starts them together) swapping restored the wrong console
 * when they finished out of order, and every later line in the process kept
 * landing in an old run's log. Lines logged outside any job are not captured.
 */
type Persist = (level: string, message: string) => void;

const currentRun = new AsyncLocalStorage<Persist>();
let consoleWrapped = false;

function wrapConsoleOnce() {
  if (consoleWrapped) return;
  consoleWrapped = true;
  for (const [method, level] of [["log", "info"], ["warn", "warn"], ["error", "error"]] as const) {
    const original = console[method].bind(console);
    console[method] = (...args: unknown[]) => {
      original(...args);
      currentRun.getStore()?.(level, args.map(String).join(" "));
    };
  }
}

export type TrackedJob = {
  runId: string;
  /** Settles when the job ends (never rejects): null on success, the error message on failure. */
  done: Promise<string | null>;
};

/**
 * Starts `fn` as a tracked JobRun and returns once the run row exists; the
 * work continues in the background. `done` says when and how it ended.
 */
export async function startTrackedJob(jobName: string, fn: (runId: string) => Promise<void>): Promise<TrackedJob> {
  wrapConsoleOnce();
  const [jobRun] = await db
    .insert(jobRuns)
    .values({ job: jobName, status: "RUNNING" })
    .returning({ id: jobRuns.id });

  const runId = jobRun.id;

  // Persist a log entry fire-and-forget (errors silently ignored so they
  // don't interrupt the job itself).
  const persist: Persist = (level, message) => {
    db.insert(jobLogs).values({ jobRunId: runId, level, message }).catch(() => {});
  };

  const done = currentRun
    .run(persist, async () => fn(runId))
    .then(async () => {
      await db.update(jobRuns).set({ status: "SUCCESS", finishedAt: new Date() }).where(eq(jobRuns.id, runId));
      return null;
    })
    .catch(async (err: unknown) => {
      const msg = serializeError(err);
      // Persist the unhandled error as an ERR log line so it's visible in the terminal
      await db.insert(jobLogs).values({ jobRunId: runId, level: "error", message: msg }).catch(() => {});
      await db
        .update(jobRuns)
        .set({ status: "FAILED", finishedAt: new Date(), error: msg })
        .where(eq(jobRuns.id, runId))
        .catch(() => {});
      return msg;
    });

  return { runId, done };
}

/**
 * Wraps a job function with full DB tracking. Returns immediately once the
 * JobRun row is created (caller gets the run id); the actual work happens in
 * the background.
 */
export async function withJobTracking(jobName: string, fn: (runId: string) => Promise<void>): Promise<string> {
  return (await startTrackedJob(jobName, fn)).runId;
}
