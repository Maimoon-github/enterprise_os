/**
 * Apply CRM classifications that were proposed but never reviewed.
 *
 * Run with: bun --conditions=react-server scripts/apply-pending-crm-classifications.ts [--dry-run]
 *
 * Relaxing the review policy (scripts/relax-crm-classification-review.ts) only
 * changes what happens to the NEXT reply. Records classified while the policy
 * was strict keep a `proposed` classification and a NULL category — 61 of them
 * at the time this was written, which is why they all rendered as "Other".
 *
 * Classification is enqueued from exactly one place (a new inbound message) and
 * re-running it would not help: recordAiClassificationInTransaction treats a
 * non-failed classification for the same message and context version as
 * strictly idempotent, so the model would run and its answer be discarded.
 * The proposals already on disk are what has to be applied.
 *
 * This walks the same steps the live path would have taken had the policy been
 * permissive: mark the classification applied, write the category onto the
 * record, start a sequence run if the subcategory has one, and enqueue the
 * draft job either way. It re-uses the production helpers so it cannot drift
 * from them. Safe to re-run — records that already have a category are skipped.
 *
 * Bun loads .env.local automatically.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { runScriptInOrganization } from "./lib/organization";
import { and, desc, eq, isNull } from "drizzle-orm";
import { db } from "../src/lib/db";
import { appendCrmEvent } from "../src/lib/crm/events";
import { enqueueCrmJobInTransaction } from "../src/lib/crm/queue";
import { withCrmTransaction } from "../src/lib/crm/repository";
import { lockCrmRecord } from "../src/lib/crm/records";
import { startSequenceRunInTransaction } from "../src/lib/crm/sequences";
import {
  crmClassifications,
  crmConversationMessages,
  crmConversations,
  crmRecords,
} from "../src/lib/crm/schema";

const dryRun = process.argv.includes("--dry-run");

async function main() {
  const pending = await db
    .select({ recordId: crmRecords.id })
    .from(crmRecords)
    .where(isNull(crmRecords.categoryKey));

  const summary = {
    candidates: pending.length,
    applied: 0,
    withSequence: 0,
    fallbackDraft: 0,
    skipped: 0,
  };

  for (const { recordId } of pending) {
    const [proposal] = await db
      .select()
      .from(crmClassifications)
      .where(and(
        eq(crmClassifications.crmRecordId, recordId),
        eq(crmClassifications.status, "proposed"),
      ))
      .orderBy(desc(crmClassifications.createdAt))
      .limit(1);

    if (!proposal?.proposedCategoryKey) {
      summary.skipped += 1;
      continue;
    }

    if (dryRun) {
      summary.applied += 1;
      console.log(
        `would apply ${proposal.proposedCategoryKey} to ${recordId} (confidence ${proposal.confidence})`,
      );
      continue;
    }

    await withCrmTransaction(async (tx) => {
      const record = await lockCrmRecord(tx, recordId);
      // Another run, or a fresh reply, may have classified this already.
      if (record.categoryKey || !record.latestInboundMessageId) {
        summary.skipped += 1;
        return;
      }

      const now = new Date();
      await tx.update(crmClassifications).set({
        status: "auto_applied",
        appliedCategoryKey: proposal.proposedCategoryKey,
        appliedSubcategoryId: proposal.proposedSubcategoryId,
        updatedAt: now,
      }).where(eq(crmClassifications.id, proposal.id));

      const [updated] = await tx.update(crmRecords).set({
        categoryKey: proposal.proposedCategoryKey,
        subcategoryId: proposal.proposedSubcategoryId,
        categorySource: "ai" as const,
        categoryLocked: false,
        workflowState: "waiting" as const,
        nextActionAt: now,
        updatedAt: now,
      }).where(eq(crmRecords.id, record.id)).returning();
      if (!updated) throw new Error(`CRM record ${record.id} update returned no row`);

      await appendCrmEvent(tx, {
        personId: updated.personId,
        crmRecordId: updated.id,
        pipelineId: updated.pipelineId,
        eventType: "classification.auto_applied",
        actorType: "ai",
        actorRef: proposal.model,
        fromData: { categoryKey: null, subcategoryId: null },
        toData: {
          classificationId: proposal.id,
          categoryKey: proposal.proposedCategoryKey,
          subcategoryId: proposal.proposedSubcategoryId,
        },
        meta: { backfill: "apply-pending-crm-classifications" },
        contextVersion: updated.contextVersion,
      });

      const [conversation] = await tx
        .select({ id: crmConversations.id })
        .from(crmConversationMessages)
        .innerJoin(crmConversations, eq(crmConversations.id, crmConversationMessages.conversationId))
        .where(and(
          eq(crmConversationMessages.id, updated.latestInboundMessageId!),
          eq(crmConversations.crmRecordId, updated.id),
        ))
        .limit(1);
      if (!conversation) {
        summary.skipped += 1;
        return;
      }

      const started = await startSequenceRunInTransaction(tx, {
        recordId: updated.id,
        conversationId: conversation.id,
        triggerMessageId: updated.latestInboundMessageId!,
        expectedContextVersion: updated.contextVersion,
        actorType: "ai",
      });

      const firstStep = started?.stepRuns[0];
      await enqueueCrmJobInTransaction(tx, {
        kind: "initial_draft",
        entityId: proposal.id,
        payload: firstStep ? { stepRunId: firstStep.id } : { recordId: updated.id },
      });

      summary.applied += 1;
      if (firstStep) summary.withSequence += 1;
      else summary.fallbackDraft += 1;
    });
  }

  console.table([summary]);
  if (dryRun) console.log("\ndry run — nothing was written");
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
