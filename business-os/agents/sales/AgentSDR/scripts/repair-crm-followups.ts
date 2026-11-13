/**
 * Repair follow-up state left behind by two CRM sequencing bugs.
 *
 * Run with: bun --conditions=react-server scripts/repair-crm-followups.ts [--dry-run]
 *
 * Until 19 Sep 2026 two things were true at once:
 *
 *  1. `sendDraft` treated any draft without a step link — which is every reply
 *     typed in the LinkedIn inbox — as the operator going off-script. It
 *     interrupted the active sequence run and cancelled every follow-up, so a
 *     lead replied to from the inbox never got a follow-up. sendDraft now adopts
 *     the pending step instead (adoptCurrentSequenceStepInTransaction).
 *
 *  2. `enqueueDueFollowupJobs` drafted any follow-up whose dueAt had passed,
 *     and dueAt is set for every step at run start. So three days after
 *     classification a "follow-up" was drafted under a reply nobody had sent.
 *     The enqueuer is now gated on the run's current step.
 *
 * Part A undoes (2): a follow-up step run that is awaiting review while the
 * run's current position is still behind it goes back to `scheduled` and its
 * draft goes stale. The reply draft on the same record is untouched and is
 * what the Action Required list shows again.
 *
 * Part B undoes (1) for records where it still matters: the run was
 * interrupted by an inbox send, the lead has not written back since, and the
 * record is otherwise untouched. A new run starts at step 2 with every dueAt
 * measured from the actual send, exactly as if the send had adopted the step.
 * Steps already past due get drafted by the worker on its next tick.
 *
 * Safe to re-run: A matches nothing once repaired, B skips records with an
 * active run. Bun loads .env.local automatically.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { runScriptInOrganization } from "./lib/organization";
import { and, asc, desc, eq, gt, inArray, sql } from "drizzle-orm";
import { db } from "../src/lib/db";
import { appendCrmEvent } from "../src/lib/crm/events";
import { isPersonDoNotContact } from "../src/lib/crm/policies";
import { withCrmTransaction } from "../src/lib/crm/repository";
import { lockCrmRecord } from "../src/lib/crm/records";
import { startSequenceRunInTransaction } from "../src/lib/crm/sequences";
import {
  crmConversationMessages,
  crmConversations,
  crmDrafts,
  crmEvents,
  crmJobs,
  crmRecords,
  crmSequenceRuns,
  crmSequenceStepRuns,
  crmSequenceSteps,
} from "../src/lib/crm/schema";

const dryRun = process.argv.includes("--dry-run");
const ACTOR = "scripts/repair-crm-followups";

async function partA(): Promise<number> {
  const premature = await db
    .select({
      stepRunId: crmSequenceStepRuns.id,
      draftId: crmSequenceStepRuns.draftId,
      recordId: crmSequenceRuns.crmRecordId,
      position: crmSequenceSteps.position,
      currentPosition: crmSequenceRuns.currentStepPosition,
    })
    .from(crmSequenceStepRuns)
    .innerJoin(crmSequenceRuns, eq(crmSequenceRuns.id, crmSequenceStepRuns.sequenceRunId))
    .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
    .where(and(
      eq(crmSequenceRuns.status, "active"),
      eq(crmSequenceSteps.stepType, "follow_up"),
      inArray(crmSequenceStepRuns.status, ["drafting", "awaiting_review", "failed"]),
      gt(crmSequenceSteps.position, crmSequenceRuns.currentStepPosition),
    ));
  console.log(`A: ${premature.length} follow-up step(s) drafted ahead of their run's current step`);
  if (dryRun) return premature.length;

  for (const row of premature) {
    await withCrmTransaction(async (tx) => {
      const record = await lockCrmRecord(tx, row.recordId);
      const now = new Date();
      if (row.draftId) {
        await tx.update(crmDrafts).set({ status: "stale", updatedAt: now })
          .where(and(eq(crmDrafts.id, row.draftId), inArray(crmDrafts.status, ["generating", "awaiting_review", "failed"])));
      }
      await tx.update(crmSequenceStepRuns)
        .set({ status: "scheduled", draftId: null, lastError: null, updatedAt: now })
        .where(eq(crmSequenceStepRuns.id, row.stepRunId));
      // The step's drafting job already ran. crm_jobs is unique per (kind,
      // entity) and the enqueuer inserts ON CONFLICT DO NOTHING, so unless
      // that row goes the step can never be drafted again once it is due.
      await tx.delete(crmJobs).where(and(
        eq(crmJobs.kind, "due_followup_draft"),
        eq(crmJobs.entityType, "sequence_step_run"),
        eq(crmJobs.entityId, row.stepRunId),
        inArray(crmJobs.status, ["succeeded", "failed"]),
      ));
      await appendCrmEvent(tx, {
        personId: record.personId, crmRecordId: record.id, pipelineId: record.pipelineId,
        eventType: "sequence.step_rescheduled", actorType: "system", actorRef: ACTOR,
        fromData: { stepRunId: row.stepRunId, status: "awaiting_review", draftId: row.draftId },
        toData: { stepRunId: row.stepRunId, status: "scheduled" },
        meta: { reason: "drafted_before_previous_step_sent", position: row.position, currentPosition: row.currentPosition },
        contextVersion: record.contextVersion,
      });
    });
  }
  return premature.length;
}

async function partB(): Promise<{ restarted: number; skipped: number }> {
  // The interruption event is written in the same transaction as the send, so
  // its timestamp is the send time.
  const interruptions = await db
    .select({
      recordId: crmEvents.crmRecordId,
      sentAt: crmEvents.createdAt,
      runId: sql<string>`${crmEvents.fromData}->>'sequenceRunId'`,
    })
    .from(crmEvents)
    .where(and(
      eq(crmEvents.eventType, "sequence.interrupted"),
      sql`${crmEvents.meta}->>'reason' = 'manual_outbound_send'`,
    ))
    .orderBy(desc(crmEvents.createdAt));

  const seen = new Set<string>();
  let restarted = 0;
  let skipped = 0;
  for (const interruption of interruptions) {
    if (!interruption.recordId || seen.has(interruption.recordId)) continue;
    seen.add(interruption.recordId);
    const [record] = await db.select().from(crmRecords).where(eq(crmRecords.id, interruption.recordId)).limit(1);
    const [run] = await db.select().from(crmSequenceRuns).where(eq(crmSequenceRuns.id, interruption.runId)).limit(1);
    if (!record || !run) { skipped += 1; continue; }

    const skip = (why: string) => {
      skipped += 1;
      console.log(`B: skip ${record.id} — ${why}`);
    };
    if (record.workflowState !== "idle") { skip(`state is ${record.workflowState}`); continue; }
    if (record.latestInboundMessageId !== run.triggerMessageId) { skip("a newer reply arrived"); continue; }
    const [active] = await db.select({ id: crmSequenceRuns.id }).from(crmSequenceRuns)
      .where(and(eq(crmSequenceRuns.crmRecordId, record.id), eq(crmSequenceRuns.status, "active"))).limit(1);
    if (active) { skip("already has an active run"); continue; }
    const [laterInbound] = await db.select({ id: crmConversationMessages.id }).from(crmConversationMessages)
      .innerJoin(crmConversations, eq(crmConversations.id, crmConversationMessages.conversationId))
      .where(and(
        eq(crmConversations.crmRecordId, record.id),
        eq(crmConversationMessages.direction, "inbound"),
        gt(crmConversationMessages.sentAt, interruption.sentAt),
      )).limit(1);
    if (laterInbound) { skip("lead replied after the send"); continue; }
    if (await isPersonDoNotContact(db, record.personId)) { skip("do not contact"); continue; }

    const plan = `${record.id} run ${run.id} → restart from step 2, clock from ${interruption.sentAt.toISOString()}`;
    if (dryRun) { console.log(`B: would restart ${plan}`); restarted += 1; continue; }

    try {
      await withCrmTransaction(async (tx) => {
        const current = await lockCrmRecord(tx, record.id);
        const started = await startSequenceRunInTransaction(tx, {
          recordId: current.id,
          conversationId: run.conversationId,
          triggerMessageId: run.triggerMessageId,
          expectedContextVersion: current.contextVersion,
          startStepPosition: 2,
          actorType: "authenticated_operator",
          actorRef: ACTOR,
        });
        if (!started) throw new Error("sequence no longer resolves for this record");
        // startSequenceRun measures dueAt from now; re-measure from the send.
        const steps = await tx.select({ stepRunId: crmSequenceStepRuns.id, delay: crmSequenceSteps.delayMinutes })
          .from(crmSequenceStepRuns)
          .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
          .where(eq(crmSequenceStepRuns.sequenceRunId, started.run.id))
          .orderBy(asc(crmSequenceSteps.position));
        let cumulative = 0;
        let firstDue: Date | null = null;
        const now = new Date();
        for (const step of steps) {
          cumulative += step.delay;
          const dueAt = new Date(interruption.sentAt.getTime() + cumulative * 60_000);
          firstDue ??= dueAt;
          await tx.update(crmSequenceStepRuns).set({ dueAt, updatedAt: now })
            .where(eq(crmSequenceStepRuns.id, step.stepRunId));
        }
        // Same write sendDraft makes after a step send (it does not go through
        // the transition table either, which has no idle → waiting edge).
        await tx.update(crmRecords)
          .set({ workflowState: "waiting", nextActionAt: firstDue, updatedAt: now })
          .where(eq(crmRecords.id, current.id));
        await appendCrmEvent(tx, {
          personId: current.personId, crmRecordId: current.id, pipelineId: current.pipelineId,
          eventType: "workflow.state_changed", actorType: "system", actorRef: ACTOR,
          fromData: { workflowState: "idle" },
          toData: { workflowState: "waiting", nextActionAt: firstDue?.toISOString() ?? null, sequenceRunId: started.run.id },
          meta: { reason: "followups_restored_after_inbox_send", interruptedRunId: run.id, sentAt: interruption.sentAt.toISOString() },
          contextVersion: current.contextVersion,
        });
      });
      console.log(`B: restarted ${plan}`);
      restarted += 1;
    } catch (error) {
      skip(`restart failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  return { restarted, skipped };
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  console.log(dryRun ? "dry run — nothing will be written" : "applying repairs");
  const rescheduled = await partA();
  const { restarted, skipped } = await partB();
  console.log(`done: ${rescheduled} follow-up(s) rescheduled, ${restarted} run(s) restarted, ${skipped} skipped`);
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
