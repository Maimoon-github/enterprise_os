/**
 * Retry the AI classification of records stuck in "Processing error".
 *
 * Run with: bun --conditions=react-server scripts/retry-crm-failed-classifications.ts [--dry-run]
 *
 * When the model provider refuses every call (15–21 Oct 2026: MiniMax's token
 * plan ran out, "402 Provider returned error"), each new reply's
 * classification job fails its three attempts and the record moves to
 * `error`, with no draft. Once the model is fixed in Settings → AI provider,
 * this puts those jobs back on the queue: a record in `error` whose latest
 * inbound message's classification job failed gets it requeued against the
 * record's current context. The worker classifies it on its next tick,
 * replaces the failed classification row in place, and drafts as usual.
 *
 * Safe to re-run: a job already queued or succeeded is left alone.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { runScriptInOrganization } from "./lib/organization";
import { and, eq } from "drizzle-orm";
import { db } from "../src/lib/db";
import { enqueueCrmJobInTransaction } from "../src/lib/crm/queue";
import { withCrmTransaction } from "../src/lib/crm/repository";
import { lockCrmRecord } from "../src/lib/crm/records";
import { crmConversationMessages, crmJobs, crmRecords } from "../src/lib/crm/schema";
import { inOrg } from "../src/lib/tenancy/scope";

const dryRun = process.argv.includes("--dry-run");

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  console.log(dryRun ? "dry run — nothing will be written" : "requeueing failed classifications");
  const stuck = await db
    .select({
      recordId: crmRecords.id,
      messageId: crmJobs.entityId,
      conversationId: crmConversationMessages.conversationId,
      lastError: crmJobs.lastError,
    })
    .from(crmRecords)
    .innerJoin(crmJobs, and(
      eq(crmJobs.kind, "classification"),
      eq(crmJobs.entityType, "message"),
      eq(crmJobs.entityId, crmRecords.latestInboundMessageId),
    ))
    .innerJoin(crmConversationMessages, eq(crmConversationMessages.id, crmJobs.entityId))
    .where(and(inOrg(crmRecords), eq(crmRecords.workflowState, "error"), eq(crmJobs.status, "failed")));
  console.log(`${stuck.length} record(s) in error with a failed classification of their latest reply`);

  let requeued = 0;
  for (const row of stuck) {
    console.log(`${row.recordId}: ${row.lastError ?? "(no error recorded)"}`);
    if (dryRun) continue;
    await withCrmTransaction(async (tx) => {
      const record = await lockCrmRecord(tx, row.recordId);
      if (record.workflowState !== "error" || record.latestInboundMessageId !== row.messageId) {
        console.log(`  skip — record moved on since the scan`);
        return;
      }
      const { created } = await enqueueCrmJobInTransaction(tx, {
        kind: "classification",
        entityId: row.messageId,
        payload: {
          crmRecordId: record.id,
          conversationId: row.conversationId,
          expectedContextVersion: record.contextVersion,
        },
        requeueCompleted: true,
      });
      if (created) requeued += 1;
      console.log(`  ${created ? "requeued" : "already queued"}`);
    });
  }
  console.log(`done: ${requeued} classification job(s) requeued`);
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
