/**
 * Guarded, in-place compatibility rollback for the unified People migration.
 *
 * This deliberately does one reversible schema operation only: make the two
 * Person references nullable so the pre-cutover runtime can start. It never
 * deletes data, drops columns/indexes/tables, or calls a provider.
 *
 * Dry-run/check:
 *   bun --conditions=react-server scripts/rollback-people-migration.ts \
 *     --phase=check --run-id=<id> --expected-database=<db> \
 *     --expected-host=<host> --expected-app-sha=<sha> --backup-id=<id> \
 *     --expected-email-null-legacy=0 --expected-linkedin-null-legacy=0 \
 *     --expected-active-jobs=0
 *
 * Apply uses the exact counts from the immediately preceding check and adds:
 *   --phase=apply-schema --apply --confirm=in-place-compatibility-rollback
 */
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";

type Phase = "check" | "apply-schema" | "verify";
type Counts = {
  emailNullLegacy: number;
  linkedinNullLegacy: number;
  activeJobs: number;
  runningSearches: number;
  queuedEmailRows: number;
};

const CONFIRMATION = "in-place-compatibility-rollback";
const arg = (name: string) => process.argv.find((value) => value.startsWith(`--${name}=`))?.slice(name.length + 3);
const required = (name: string) => {
  const value = arg(name)?.trim();
  if (!value) throw new Error(`--${name}=<value> is required`);
  return value;
};
const expectedInteger = (name: string) => {
  const raw = required(name);
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`--${name} must be a non-negative integer`);
  return value;
};

function appSha() {
  return process.env.APP_GIT_SHA
    ?? process.env.VERCEL_GIT_COMMIT_SHA
    ?? process.env.RAILWAY_GIT_COMMIT_SHA
    ?? process.env.GIT_SHA;
}

function safeRunId(value: string) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(value)) {
    throw new Error("--run-id may contain only letters, digits, dot, underscore, and dash");
  }
  return value;
}

async function inspect(client: Client) {
  const { rows: identity } = await client.query<{ database: string; host: string | null }>(
    `SELECT current_database() AS database, inet_server_addr()::text AS host`,
  );
  const { rows: countRows } = await client.query<Counts>(`
      SELECT
        (SELECT count(*)::int FROM outreach_leads WHERE email IS NULL) AS "emailNullLegacy",
        (SELECT count(*)::int FROM "Lead" WHERE "linkedinUrl" IS NULL) AS "linkedinNullLegacy",
        (SELECT count(*)::int FROM "JobRun"
          WHERE status = 'RUNNING' AND "finishedAt" IS NULL) AS "activeJobs",
        (SELECT count(*)::int FROM "SearchQuery" WHERE status = 'RUNNING') AS "runningSearches",
        (SELECT count(*)::int FROM outreach_mailbox_queue) AS "queuedEmailRows"
    `);
  const { rows: columns } = await client.query<{ table_name: string; column_name: string; is_nullable: "YES" | "NO" }>(`
      SELECT table_name, column_name, is_nullable
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND (table_name, column_name) IN (('outreach_leads', 'person_id'), ('Lead', 'personId'))
      ORDER BY table_name, column_name
    `);
  const { rows: memberTable } = await client.query<{ present: boolean }>(`
      SELECT to_regclass('public.campaign_members') IS NOT NULL AS present
    `);
  return {
    database: identity[0]?.database ?? "",
    serverHost: identity[0]?.host ?? null,
    counts: countRows[0],
    personColumns: columns,
    campaignMembers: memberTable[0]?.present ? "present" : "absent_expected",
  };
}

async function main() {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) throw new Error("DATABASE_URL is not set");
  const phase = (arg("phase") ?? "check") as Phase;
  if (!["check", "apply-schema", "verify"].includes(phase)) throw new Error("--phase must be check, apply-schema, or verify");
  const apply = process.argv.includes("--apply");
  if (apply !== (phase === "apply-schema")) {
    throw new Error("Only --phase=apply-schema may use --apply, and apply-schema requires it");
  }

  const runId = safeRunId(required("run-id"));
  const expectedDatabase = required("expected-database");
  const expectedHost = required("expected-host").toLowerCase();
  const expectedSha = required("expected-app-sha");
  const backupId = required("backup-id");
  const expectations = {
    emailNullLegacy: expectedInteger("expected-email-null-legacy"),
    linkedinNullLegacy: expectedInteger("expected-linkedin-null-legacy"),
    activeJobs: expectedInteger("expected-active-jobs"),
  };
  const actualSha = appSha();
  if (!actualSha || actualSha !== expectedSha) throw new Error(`Application SHA mismatch: expected ${expectedSha}, found ${actualSha ?? "unset"}`);
  const url = new URL(databaseUrl);
  if (url.hostname.toLowerCase() !== expectedHost) {
    throw new Error(`Database URL host mismatch: expected ${expectedHost}, found ${url.hostname}`);
  }
  if (apply && arg("confirm") !== CONFIRMATION) throw new Error(`Apply requires --confirm=${CONFIRMATION}`);

  const client = new Client({
    connectionString: databaseUrl,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: apply ? "agentsdr-people-compatibility-rollback" : "agentsdr-readonly-people-rollback-check",
  });
  await client.connect();
  let before: Awaited<ReturnType<typeof inspect>> | undefined;
  let after: Awaited<ReturnType<typeof inspect>> | undefined;
  try {
    await client.query(apply ? "BEGIN ISOLATION LEVEL SERIALIZABLE" : "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL lock_timeout = '5s'");
    await client.query("SET LOCAL statement_timeout = '30s'");
    if (apply) await client.query("SELECT pg_advisory_xact_lock(hashtext('agentsdr-people-compatibility-rollback'))");
    before = await inspect(client);
    if (before.database !== expectedDatabase) throw new Error(`Database mismatch: expected ${expectedDatabase}, found ${before.database}`);
    const drift = (Object.keys(expectations) as Array<keyof typeof expectations>)
      .filter((key) => before!.counts[key] !== expectations[key])
      .map((key) => `${key}: expected ${expectations[key]}, found ${before!.counts[key]}`);
    if (drift.length) throw new Error(`Rollback precondition drift: ${drift.join("; ")}`);
    if (before.counts.emailNullLegacy || before.counts.linkedinNullLegacy) {
      throw new Error("Old-runtime compatibility blocked: enrollments have null legacy recipient identities");
    }
    if (before.counts.activeJobs || before.counts.runningSearches) {
      throw new Error("Rollback blocked: database still reports active jobs/searches");
    }
    if (before.personColumns.length !== 2) throw new Error("Unified People schema is incomplete; expected both Person reference columns");

    if (apply) {
      await client.query("ALTER TABLE outreach_leads ALTER COLUMN person_id DROP NOT NULL");
      await client.query('ALTER TABLE "Lead" ALTER COLUMN "personId" DROP NOT NULL');
      after = await inspect(client);
      if (after.personColumns.some((column) => column.is_nullable !== "YES")) {
        throw new Error("Rollback postcondition failed: Person references are not nullable");
      }
      await client.query("COMMIT");
    } else {
      after = before;
      if (phase === "verify" && after.personColumns.some((column) => column.is_nullable !== "YES")) {
        throw new Error("Rollback verification failed: Person references are still NOT NULL");
      }
      await client.query("ROLLBACK");
    }
  } catch (error) {
    try { await client.query("ROLLBACK"); } catch { /* connection may already be closed */ }
    throw error;
  } finally {
    await client.end();
  }

  const report = {
    createdAt: new Date().toISOString(),
    runId,
    phase,
    mode: apply ? "apply" : "read-only",
    backupId,
    applicationSha: actualSha,
    expectedDatabase,
    expectedHost,
    expectations,
    before,
    after,
    mutations: apply ? ["outreach_leads.person_id DROP NOT NULL", "Lead.personId DROP NOT NULL"] : [],
    explicitlyPreserved: ["people", "companies", "messages", "connections", "webhooks", "legacy identity columns", "indexes", "foreign keys"],
  };
  const directory = resolve("reports/migration/rollback");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const reportPath = resolve(directory, `${runId}-${phase}.json`);
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { encoding: "utf8", mode: 0o600, flag: "wx" });
  console.log(JSON.stringify({ passed: true, reportPath, phase, counts: before?.counts }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
