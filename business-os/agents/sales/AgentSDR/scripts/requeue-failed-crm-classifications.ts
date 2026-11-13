/**
 * Requeue classification jobs that failed for a reason that has since been fixed.
 *
 * Run with: bun --conditions=react-server scripts/requeue-failed-crm-classifications.ts [--dry-run]
 *
 * Between 10 and 16 Sep 2026 every classification failed with OpenRouter's
 * "404 No endpoints found that can handle the requested parameters": the default
 * model had been switched to a provider that does not support strict JSON-schema
 * structured outputs, and the request pinned that parameter as required. The
 * fix (json_object fallback in src/lib/ai/server/jsonCompletion.ts) only helps
 * the NEXT reply; the 33 records already parked in `error` have a terminal
 * `failed` job and nothing in the UI can retry one.
 *
 * A job is requeued only when it still describes the record's current state:
 * its entity is the record's latest inbound message and its expectedContextVersion
 * matches. A successful re-run replaces the earlier `failed` classification row
 * (recordAiClassificationInTransaction lets a failed attempt be retried) and moves
 * the record out of `error`. Jobs whose context moved on are reported and left
 * alone — the handler would reject them as stale anyway.
 *
 * Bun loads .env.local automatically; override DATABASE_URL if that file points
 * at a retired host.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset
 * (bun run --conditions=react-server).
 */
import { runScriptInOrganization } from "./lib/organization";
import { and, eq } from "drizzle-orm";
import { db } from "../src/lib/db";
import { requeueFailedCrmJob } from "../src/lib/crm/queue";
import { crmJobs, crmRecords } from "../src/lib/crm/schema";

const dryRun = process.argv.includes("--dry-run");

async function main() {
  const candidates = await db
    .select({
      jobId: crmJobs.id,
      payload: crmJobs.payload,
      lastError: crmJobs.lastError,
      recordId: crmRecords.id,
      contextVersion: crmRecords.contextVersion,
    })
    .from(crmJobs)
    .innerJoin(crmRecords, eq(crmRecords.latestInboundMessageId, crmJobs.entityId))
    .where(and(
      eq(crmJobs.kind, "classification"),
      eq(crmJobs.status, "failed"),
      eq(crmRecords.workflowState, "error"),
    ));

  const summary = { candidates: candidates.length, requeued: 0, staleContext: 0 };
  const errors = new Map<string, number>();

  for (const candidate of candidates) {
    const expected = Number(candidate.payload.expectedContextVersion);
    if (Number.isFinite(expected) && expected !== candidate.contextVersion) {
      summary.staleContext += 1;
      continue;
    }
    const reason = (candidate.lastError ?? "unknown").slice(0, 80);
    errors.set(reason, (errors.get(reason) ?? 0) + 1);
    if (!dryRun) await requeueFailedCrmJob(candidate.jobId);
    summary.requeued += 1;
  }

  console.table([summary]);
  console.table([...errors].map(([error, count]) => ({ error, count })));
  if (dryRun) console.log("\ndry run — nothing was written");
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
