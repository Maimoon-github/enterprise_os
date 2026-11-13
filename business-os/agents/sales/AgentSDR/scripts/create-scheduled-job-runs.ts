/**
 * The in-process scheduler's slot claims (src/lib/scheduler/), which replace
 * the cron container. Matches src/lib/scheduler/schema.ts; global (not
 * organization-scoped) in src/lib/tenancy/registry.ts.
 *
 * Run with:  bun scripts/create-scheduled-job-runs.ts
 * In Docker: docker compose exec app agentsdr-entrypoint bun scripts/create-scheduled-job-runs.ts
 *            (the entrypoint supplies DATABASE_URL for the bundled database)
 *
 * - scheduled_job_runs: one row per (job, slot) — whoever inserts it runs
 *   that slot. Until it exists the app runs no scheduled jobs in-process and
 *   logs a warning; the job endpoints keep working as before.
 *
 * Additive and re-runnable: every statement is guarded. Uses Bun's built-in
 * PostgreSQL client and no packages, so it also runs inside the Docker image.
 */
import { SQL } from "bun";

const STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS scheduled_job_runs (
     job text NOT NULL,
     slot timestamptz NOT NULL,
     started_at timestamptz NOT NULL DEFAULT now(),
     finished_at timestamptz,
     error text,
     CONSTRAINT scheduled_job_runs_pkey PRIMARY KEY (job, slot)
   )`,
];

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set — check .env.local");
  const sql = new SQL(url, {
    max: 1,
    tls: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });
  try {
    await sql.unsafe("SET lock_timeout = '5s'");
    await sql.unsafe("SET statement_timeout = '2min'");
    for (const statement of STATEMENTS) await sql.unsafe(statement);
    const [{ present }] = await sql`select to_regclass('public.scheduled_job_runs') is not null as present`;
    console.log(`scheduled_job_runs ${present ? "present" : "MISSING"}`);
    if (!present) process.exitCode = 1;
  } finally {
    await sql.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
