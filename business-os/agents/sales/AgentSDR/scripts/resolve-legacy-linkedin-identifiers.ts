/**
 * Controlled, resumable resolver for active LinkedIn Leads after People
 * backfill. It performs profile lookups only; invitations and messages are
 * never sent by this command.
 *
 * Dry run:
 *   bun --conditions=react-server scripts/resolve-legacy-linkedin-identifiers.ts
 * Apply:
 *   bun --conditions=react-server scripts/resolve-legacy-linkedin-identifiers.ts \
 *     --apply --expected-actionable=N --passes=1 --confirm=outbound-workers-paused
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { runScriptInOrganization } from "./lib/organization";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { and, asc, count, eq, isNotNull, sql } from "drizzle-orm";
import { db } from "../src/lib/db";
import { campaigns, leads, linkedInAccounts } from "../src/lib/linkedin/schema";
import { resolveProfiles } from "../src/functions/resolveProfiles";

const CONFIRMATION = "outbound-workers-paused";

function integerArg(name: string, fallback: number | null = null) {
  const raw = process.argv.find((value) => value.startsWith(`${name}=`))?.slice(name.length + 1);
  if (raw === undefined) return fallback;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < 0) throw new Error(`${name} must be a non-negative integer`);
  return parsed;
}

const targetLeadId = process.argv.find((value) => value.startsWith("--lead-id="))?.slice("--lead-id=".length) || null;

async function actionableCount(leadId: string | null = null) {
  const [row] = await db
    .select({ count: count() })
    .from(leads)
    .innerJoin(campaigns, eq(leads.campaignId, campaigns.id))
    .where(and(
      eq(campaigns.status, "ACTIVE"),
      eq(leads.status, "PENDING"),
      isNotNull(leads.personId),
      isNotNull(leads.sourceLinkedinIdentifier),
      leadId ? eq(leads.id, leadId) : undefined,
    ));
  return Number(row?.count ?? 0);
}

async function main() {
  const apply = process.argv.includes("--apply");
  const requireZero = process.argv.includes("--require-zero");
  const passes = integerArg("--passes", 1)!;
  if (passes < 1 || passes > 100) throw new Error("--passes must be between 1 and 100");

  const [{ database }] = await db.execute<{ database: string }>(sql`select current_database() as database`);
  const expectedDatabase = process.argv.find((value) => value.startsWith("--expected-database="))?.slice("--expected-database=".length);
  const before = await actionableCount(targetLeadId);
  if (!apply) {
    console.log(JSON.stringify({ mode: "dry-run", database, actionable: before, providerCalls: 0 }, null, 2));
    return;
  }
  const expected = integerArg("--expected-actionable");
  if (expected === null || !expectedDatabase || !process.argv.includes(`--confirm=${CONFIRMATION}`)) {
    throw new Error(`Apply requires --expected-database=<name>, --expected-actionable=N and --confirm=${CONFIRMATION}`);
  }
  if (database !== expectedDatabase) throw new Error(`Database guard failed: expected ${expectedDatabase}, got ${database}`);
  if (before !== expected) throw new Error(`Resolver count changed: expected ${expected}, found ${before}`);

  const accounts = await db
    .select()
    .from(linkedInAccounts)
    .where(and(eq(linkedInAccounts.status, "CONNECTED"), eq(linkedInAccounts.limitReached, false)))
    .orderBy(asc(linkedInAccounts.createdAt));
  if (before > 0 && accounts.length === 0) throw new Error("No connected LinkedIn accounts are available for profile resolution");

  let previous = before;
  let completedPasses = 0;
  for (let pass = 1; pass <= passes && previous > 0; pass++) {
    for (const account of accounts) {
      await resolveProfiles(account, { activeCampaignsOnly: true, leadId: targetLeadId ?? undefined });
      if (targetLeadId && await actionableCount(targetLeadId) === 0) break;
    }
    completedPasses = pass;
    const remaining = await actionableCount(targetLeadId);
    if (remaining >= previous) break;
    previous = remaining;
  }

  const after = await actionableCount(targetLeadId);
  const report = {
    createdAt: new Date().toISOString(),
    mode: "apply",
    expectedActionable: expected,
    database,
    leadId: targetLeadId,
    before,
    resolved: before - after,
    remaining: after,
    completedPasses,
  };
  await mkdir(resolve("reports/migration"), { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const reportPath = resolve(`reports/migration/linkedin-resolution-${timestamp}.json`);
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { flag: "wx", mode: 0o600 });
  console.log(JSON.stringify({ ...report, reportPath }, null, 2));
  if (requireZero && after > 0) process.exitCode = 2;
}

runScriptInOrganization(main).catch((error) => {
  console.error(error);
  process.exit(1);
});
