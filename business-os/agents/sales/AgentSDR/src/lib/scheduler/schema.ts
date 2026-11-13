import { primaryKey, pgTable, text, timestamp } from "drizzle-orm/pg-core";

/**
 * One row per scheduled run: the claim that makes a slot run at most once
 * across restarts, overlapping instances and external cron calls
 * (src/lib/scheduler/claims.ts). Platform-wide, not organization-scoped: a
 * per-organization job carries the organization in its name
 * (`daily-rollover:<organization id>`). Built by
 * scripts/create-scheduled-job-runs.ts; global in src/lib/tenancy/registry.ts.
 */
export const scheduledJobRuns = pgTable(
  "scheduled_job_runs",
  {
    job: text("job").notNull(),
    /** The instant the run belongs to (see slots.ts), not when it ran. */
    slot: timestamp("slot", { withTimezone: true }).notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
    /** Why it failed, or why it did not run ("not run: …"); null when it succeeded. */
    error: text("error"),
  },
  (table) => [primaryKey({ name: "scheduled_job_runs_pkey", columns: [table.job, table.slot] })],
);
