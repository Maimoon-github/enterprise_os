/**
 * Repair records a human reclassified before 20 Sep 2026.
 *
 * Run with: bun --conditions=react-server scripts/repair-crm-reclassified-drafts.ts [--dry-run]
 *
 * applyHumanClassification re-applies the same classification row, and its
 * initial_draft job had already succeeded for the previous run's step, so the
 * enqueue was a no-op: the new run's reply step never got a draft. Meanwhile
 * the drafts written for the old context stayed "awaiting review" and failed
 * with a stale-context error on send. Both are fixed in the live path (the job
 * is requeued; old drafts go stale). This applies the same to what is already
 * in the database:
 *
 *  A. open drafts whose expected context version no longer matches the record
 *     go stale;
 *  B. active runs whose reply step is still `scheduled` with no draft get
 *     their initial_draft job requeued, so the worker drafts it on its next
 *     tick.
 *
 * Safe to re-run. Bun loads .env.local automatically.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { runScriptInOrganization } from "./lib/organization";
import { and, desc, eq, inArray, isNull, ne } from "drizzle-orm";
import { db } from "../src/lib/db";
import { appendCrmEvent } from "../src/lib/crm/events";
import { enqueueCrmJobInTransaction } from "../src/lib/crm/queue";
import { withCrmTransaction } from "../src/lib/crm/repository";
import { lockCrmRecord } from "../src/lib/crm/records";
import {
  crmClassifications,
  crmDrafts,
  crmRecords,
  crmSequenceRuns,
  crmSequenceStepRuns,
  crmSequenceSteps,
} from "../src/lib/crm/schema";

const dryRun = process.argv.includes("--dry-run");
const ACTOR = "scripts/repair-crm-reclassified-drafts";

async function partA(): Promise<number> {
  const stale = await db
    .select({ draftId: crmDrafts.id, recordId: crmDrafts.crmRecordId, draftVersion: crmDrafts.expectedContextVersion, recordVersion: crmRecords.contextVersion })
    .from(crmDrafts)
    .innerJoin(crmRecords, eq(crmRecords.id, crmDrafts.crmRecordId))
    .where(and(
      inArray(crmDrafts.status, ["generating", "awaiting_review", "failed"]),
      ne(crmDrafts.expectedContextVersion, crmRecords.contextVersion),
    ));
  console.log(`A: ${stale.length} open draft(s) written for an older record context`);
  if (dryRun) return stale.length;
  for (const row of stale) {
    await withCrmTransaction(async (tx) => {
      const record = await lockCrmRecord(tx, row.recordId);
      await tx.update(crmDrafts).set({ status: "stale", updatedAt: new Date() }).where(eq(crmDrafts.id, row.draftId));
      await appendCrmEvent(tx, {
        personId: record.personId, crmRecordId: record.id, pipelineId: record.pipelineId,
        eventType: "draft.stale", actorType: "system", actorRef: ACTOR,
        fromData: { draftId: row.draftId, status: "awaiting_review", expectedContextVersion: row.draftVersion },
        toData: { draftId: row.draftId, status: "stale" },
        meta: { reason: "record_context_changed", contextVersion: row.recordVersion },
        contextVersion: record.contextVersion,
      });
    });
  }
  return stale.length;
}

async function partB(): Promise<number> {
  const undrafted = await db
    .select({ recordId: crmSequenceRuns.crmRecordId, stepRunId: crmSequenceStepRuns.id })
    .from(crmSequenceRuns)
    .innerJoin(crmSequenceStepRuns, eq(crmSequenceStepRuns.sequenceRunId, crmSequenceRuns.id))
    .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
    .where(and(
      eq(crmSequenceRuns.status, "active"),
      eq(crmSequenceSteps.position, 1),
      eq(crmSequenceStepRuns.status, "scheduled"),
      isNull(crmSequenceStepRuns.draftId),
    ));
  console.log(`B: ${undrafted.length} active run(s) whose reply step was never drafted`);
  if (dryRun) return undrafted.length;
  let requeued = 0;
  for (const row of undrafted) {
    await withCrmTransaction(async (tx) => {
      const record = await lockCrmRecord(tx, row.recordId);
      const [classification] = await tx.select({ id: crmClassifications.id }).from(crmClassifications)
        .where(eq(crmClassifications.crmRecordId, record.id)).orderBy(desc(crmClassifications.createdAt)).limit(1);
      if (!classification) {
        console.log(`B: skip ${record.id} — no classification to draft from`);
        return;
      }
      const { created } = await enqueueCrmJobInTransaction(tx, {
        kind: "initial_draft",
        entityId: classification.id,
        payload: { stepRunId: row.stepRunId },
        requeueCompleted: true,
      });
      if (created) requeued += 1;
      console.log(`B: ${created ? "requeued" : "already queued"} draft for ${record.id} step ${row.stepRunId}`);
    });
  }
  return requeued;
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  console.log(dryRun ? "dry run — nothing will be written" : "applying repairs");
  const staled = await partA();
  const requeued = await partB();
  console.log(`done: ${staled} draft(s) marked stale, ${requeued} draft job(s) requeued`);
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
