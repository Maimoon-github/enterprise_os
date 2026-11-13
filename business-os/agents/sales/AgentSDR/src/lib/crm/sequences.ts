import { randomUUID } from "node:crypto";
import { and, asc, count, eq, inArray, isNull, ne, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseOptionalText,
  parseRequiredText,
  parseUuid,
} from "./categories";
import { appendCrmEvent } from "./events";
import {
  CrmConflictError,
  CrmNotFoundError,
  type CrmTransaction,
  withCrmTransaction,
} from "./repository";
import { lockCrmRecord } from "./records";
import {
  crmConversations,
  crmDrafts,
  crmPipelines,
  crmRecordSequenceOverrides,
  crmRecords,
  crmSequenceRuns,
  crmSequenceStepRuns,
  crmSequenceSteps,
  crmSequenceVersions,
  crmSequences,
  crmSubcategories,
  crmSubcategorySequenceAssignments,
  type CrmSequenceStatus,
} from "./schema";
import { assertCurrentCrmContext, assertWorkflowTransition } from "./stateMachine";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

export type CrmSequenceRun = typeof crmSequenceRuns.$inferSelect;
export type CrmSequenceStepRun = typeof crmSequenceStepRuns.$inferSelect;

type SequenceSelection = {
  sequenceId: string;
  sequenceVersionId: string;
  source: "human_override" | "ai_assignment";
};

async function resolveSequenceSelection(
  tx: CrmTransaction,
  input: { recordId: string; subcategoryId: string },
): Promise<SequenceSelection | null> {
  const [override] = await tx
    .select({
      sequenceId: crmSequences.id,
      sequenceVersionId: crmSequences.latestPublishedVersionId,
      active: crmSequences.status,
    })
    .from(crmRecordSequenceOverrides)
    .innerJoin(crmSequences, eq(crmSequences.id, crmRecordSequenceOverrides.sequenceId))
    .where(and(
      inOrg(crmSequences),
      eq(crmRecordSequenceOverrides.crmRecordId, input.recordId),
      isNull(crmRecordSequenceOverrides.clearedAt),
    ))
    .limit(1);

  if (override) {
    if (override.active !== "active" || !override.sequenceVersionId) {
      throw new CrmConflictError("The record sequence override has no active published version");
    }
    return {
      sequenceId: override.sequenceId,
      sequenceVersionId: override.sequenceVersionId,
      source: "human_override",
    };
  }

  const [assigned] = await tx
    .select({
      sequenceId: crmSequences.id,
      sequenceVersionId: crmSequences.latestPublishedVersionId,
      active: crmSequences.status,
    })
    .from(crmSubcategorySequenceAssignments)
    .innerJoin(crmSequences, eq(crmSequences.id, crmSubcategorySequenceAssignments.sequenceId))
    .where(and(inOrg(crmSequences), eq(crmSubcategorySequenceAssignments.subcategoryId, input.subcategoryId)))
    .limit(1);

  if (!assigned) return null;
  if (assigned.active !== "active" || !assigned.sequenceVersionId) return null;
  return {
    sequenceId: assigned.sequenceId,
    sequenceVersionId: assigned.sequenceVersionId,
    source: "ai_assignment",
  };
}

async function cancelUnsentRunWork(tx: CrmTransaction, runId: string, now: Date): Promise<void> {
  const unsentSteps = await tx
    .select({ id: crmSequenceStepRuns.id, draftId: crmSequenceStepRuns.draftId })
    .from(crmSequenceStepRuns)
    .where(and(
      eq(crmSequenceStepRuns.sequenceRunId, runId),
      inArray(crmSequenceStepRuns.status, ["scheduled", "drafting", "awaiting_review", "failed"]),
    ));
  const draftIds = unsentSteps.flatMap((step) => step.draftId ? [step.draftId] : []);
  if (draftIds.length) {
    await tx
      .update(crmDrafts)
      .set({ status: "stale", updatedAt: now })
      .where(and(
        inArray(crmDrafts.id, draftIds),
        inArray(crmDrafts.status, ["generating", "awaiting_review", "failed"]),
      ));
  }
  if (unsentSteps.length) {
    await tx
      .update(crmSequenceStepRuns)
      .set({ status: "cancelled", updatedAt: now })
      .where(inArray(crmSequenceStepRuns.id, unsentSteps.map((step) => step.id)));
  }
}

export async function interruptActiveSequenceRunInTransaction(
  tx: CrmTransaction,
  input: { recordId: string; reason: string; contextVersion: number },
): Promise<CrmSequenceRun | null> {
  const [run] = await tx
    .select()
    .from(crmSequenceRuns)
    .where(and(eq(crmSequenceRuns.crmRecordId, input.recordId), eq(crmSequenceRuns.status, "active")))
    .limit(1)
    .for("update");
  if (!run) return null;

  const now = new Date();
  await cancelUnsentRunWork(tx, run.id, now);
  const [updated] = await tx
    .update(crmSequenceRuns)
    .set({ status: "interrupted", updatedAt: now })
    .where(eq(crmSequenceRuns.id, run.id))
    .returning();
  if (!updated) throw new Error("CRM sequence interruption did not return a row");

  const record = await lockCrmRecord(tx, input.recordId);
  await appendCrmEvent(tx, {
    personId: record.personId,
    crmRecordId: record.id,
    pipelineId: record.pipelineId,
    eventType: "sequence.interrupted",
    actorType: "system",
    fromData: { sequenceRunId: run.id, status: run.status },
    toData: { sequenceRunId: run.id, status: "interrupted" },
    meta: { reason: input.reason },
    contextVersion: input.contextVersion,
  });
  return updated;
}

/**
 * Frees a step run's slot in crm_drafts_step_run_uq (one draft per step) from
 * any draft other than `keepDraftId`. A step reset by pausing used to clear
 * its own `draftId` but leave the stale draft pointing back at it, so the
 * next draft linked to that step — adopted reply or regenerated AI draft —
 * failed the unique index. The orphan is already stale; only the link goes.
 */
export async function releaseStepRunDraftLinks(tx: CrmTransaction, stepRunId: string, keepDraftId?: string) {
  await tx.update(crmDrafts)
    .set({ sequenceStepRunId: null, updatedAt: new Date() })
    .where(and(
      eq(crmDrafts.sequenceStepRunId, stepRunId),
      ...(keepDraftId ? [ne(crmDrafts.id, keepDraftId)] : []),
    ));
}

/**
 * Makes a hand-written draft the delivery for the run's current pending step.
 *
 * A reply typed in the LinkedIn or email inbox (or the CRM page's "Create
 * draft") has no step link, and `sendDraft` used to treat every such send as
 * the operator going off-script: it interrupted the run and cancelled every
 * follow-up. In practice that draft *is* the reply — or, during a follow-up
 * window, *is* the follow-up — so it takes the step over from the AI draft,
 * which goes stale. Returns the adopted step run id, or null when the record
 * has no active run with a pending step (the caller keeps its old behaviour).
 */
export async function adoptCurrentSequenceStepInTransaction(
  tx: CrmTransaction,
  input: { recordId: string; draftId: string; contextVersion: number },
): Promise<{ stepRunId: string; position: number; replacedDraftId: string | null } | null> {
  const [run] = await tx
    .select()
    .from(crmSequenceRuns)
    .where(and(eq(crmSequenceRuns.crmRecordId, input.recordId), eq(crmSequenceRuns.status, "active")))
    .limit(1)
    .for("update");
  if (!run) return null;
  // Same "current step" rule as skipCurrentSequenceStep: the earliest unsent one.
  const [current] = await tx
    .select({ stepRun: crmSequenceStepRuns, step: crmSequenceSteps })
    .from(crmSequenceStepRuns)
    .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
    .where(and(
      eq(crmSequenceStepRuns.sequenceRunId, run.id),
      inArray(crmSequenceStepRuns.status, ["scheduled", "drafting", "awaiting_review", "failed"]),
    ))
    .orderBy(asc(crmSequenceSteps.position))
    .limit(1)
    .for("update", { of: crmSequenceStepRuns });
  if (!current) return null;

  const now = new Date();
  const replacedDraftId = current.stepRun.draftId && current.stepRun.draftId !== input.draftId
    ? current.stepRun.draftId
    : null;
  if (replacedDraftId) {
    const [replaced] = await tx
      .select({ status: crmDrafts.status })
      .from(crmDrafts)
      .where(eq(crmDrafts.id, replacedDraftId))
      .limit(1)
      .for("update");
    // A step whose draft is mid-send belongs to that send until it is
    // reconciled; leave it alone and let the caller treat this as off-script.
    if (replaced && ["sending", "delivery_uncertain"].includes(replaced.status)) return null;
    // crm_drafts_step_run_uq allows one draft per step, and regeneration
    // revises that one row rather than adding another — so the draft being
    // replaced must give up the link, not just its status.
    await tx
      .update(crmDrafts)
      .set({
        sequenceStepRunId: null,
        ...(replaced && ["generating", "awaiting_review", "failed"].includes(replaced.status)
          ? { status: "stale" as const }
          : {}),
        updatedAt: now,
      })
      .where(eq(crmDrafts.id, replacedDraftId));
  }
  await releaseStepRunDraftLinks(tx, current.stepRun.id, input.draftId);
  await tx
    .update(crmSequenceStepRuns)
    .set({ draftId: input.draftId, status: "awaiting_review", lastError: null, updatedAt: now })
    .where(eq(crmSequenceStepRuns.id, current.stepRun.id));
  await tx
    .update(crmDrafts)
    .set({ sequenceStepRunId: current.stepRun.id, updatedAt: now })
    .where(eq(crmDrafts.id, input.draftId));

  const record = await lockCrmRecord(tx, input.recordId);
  await appendCrmEvent(tx, {
    personId: record.personId,
    crmRecordId: record.id,
    pipelineId: record.pipelineId,
    eventType: "sequence.step_adopted",
    actorType: "authenticated_operator",
    fromData: { stepRunId: current.stepRun.id, draftId: replacedDraftId },
    toData: { stepRunId: current.stepRun.id, draftId: input.draftId, position: current.step.position },
    contextVersion: input.contextVersion,
  });
  return { stepRunId: current.stepRun.id, position: current.step.position, replacedDraftId };
}

export type StartSequenceRunInput = {
  recordId: string;
  conversationId: string;
  triggerMessageId: string;
  expectedContextVersion: number;
  startStepPosition?: number;
  /**
   * Start at the first follow-up: the reply step is taken as handled
   * off-thread. A sequence with no follow-ups then starts nothing — the
   * record's previous run is still cancelled — and the call returns null.
   */
  skipReply?: boolean;
  sequenceId?: string;
  actorType?: "ai" | "authenticated_operator";
  actorRef?: string | null;
};

export async function startSequenceRunInTransaction(
  tx: CrmTransaction,
  input: StartSequenceRunInput,
): Promise<{ run: CrmSequenceRun; stepRuns: CrmSequenceStepRun[] } | null> {
  const record = await lockCrmRecord(tx, input.recordId);
  assertCurrentCrmContext(record, {
    contextVersion: input.expectedContextVersion,
    latestInboundMessageId: input.triggerMessageId,
  });
  if (!record.subcategoryId || !record.categoryKey) return null;

  const [conversation] = await tx
    .select()
    .from(crmConversations)
    .where(and(
      eq(crmConversations.id, input.conversationId),
      eq(crmConversations.crmRecordId, record.id),
    ))
    .limit(1);
  if (!conversation) throw new CrmNotFoundError("CRM conversation", input.conversationId);

  let selection = await resolveSequenceSelection(tx, {
    recordId: record.id,
    subcategoryId: record.subcategoryId,
  });
  if (input.sequenceId) {
    const [manual] = await tx
      .select({ id: crmSequences.id, status: crmSequences.status, versionId: crmSequences.latestPublishedVersionId })
      .from(crmSequences)
      .where(and(inOrg(crmSequences), eq(crmSequences.id, input.sequenceId)))
      .limit(1);
    if (!manual) throw new CrmNotFoundError("CRM sequence", input.sequenceId);
    if (manual.status !== "active" || !manual.versionId) {
      throw new CrmConflictError("Sequence must be active and published");
    }
    selection = { sequenceId: manual.id, sequenceVersionId: manual.versionId, source: "human_override" };
  }
  if (!selection) return null;

  const startPosition = input.skipReply ? 2 : input.startStepPosition ?? 1;
  if (!Number.isInteger(startPosition) || startPosition < 1) {
    throw new Error("Sequence start position must be a positive integer");
  }
  const steps = await tx
    .select()
    .from(crmSequenceSteps)
    .where(and(
      eq(crmSequenceSteps.sequenceVersionId, selection.sequenceVersionId),
      sql`${crmSequenceSteps.position} >= ${startPosition}`,
    ))
    .orderBy(asc(crmSequenceSteps.position));
  if (input.skipReply && !steps.length) {
    await interruptActiveSequenceRunInTransaction(tx, {
      recordId: record.id,
      reason: "sequence_has_no_follow_ups",
      contextVersion: record.contextVersion,
    });
    return null;
  }
  if (!steps.length || steps[0]!.position !== startPosition) {
    throw new CrmConflictError("The selected published sequence has no requested start step");
  }

  const [existing] = await tx
    .select()
    .from(crmSequenceRuns)
    .where(and(eq(crmSequenceRuns.crmRecordId, record.id), eq(crmSequenceRuns.status, "active")))
    .limit(1)
    .for("update");
  const now = new Date();
  if (existing) {
    if (
      existing.sequenceVersionId === selection.sequenceVersionId
      && existing.triggerMessageId === input.triggerMessageId
      && existing.startStepPosition === startPosition
    ) {
      const existingSteps = await tx
        .select()
        .from(crmSequenceStepRuns)
        .where(eq(crmSequenceStepRuns.sequenceRunId, existing.id))
        .orderBy(asc(crmSequenceStepRuns.dueAt));
      return { run: existing, stepRuns: existingSteps };
    }
    await cancelUnsentRunWork(tx, existing.id, now);
    await tx
      .update(crmSequenceRuns)
      .set({ status: "cancelled", updatedAt: now })
      .where(eq(crmSequenceRuns.id, existing.id));
  }

  const [run] = await tx
    .insert(crmSequenceRuns)
    .values({
      organizationId: currentOrganizationId(),
      crmRecordId: record.id,
      conversationId: conversation.id,
      sequenceId: selection.sequenceId,
      sequenceVersionId: selection.sequenceVersionId,
      subcategoryId: record.subcategoryId,
      currentStepPosition: startPosition,
      startStepPosition: startPosition,
      startedBy: selection.source,
      triggerMessageId: input.triggerMessageId,
      lastInboundAtStart: record.lastInboundAt ?? now,
    })
    .returning();
  if (!run) throw new Error("CRM sequence run insert did not return a row");

  // Step 1's delay is always 0, so this only matters when a run starts at a
  // follow-up: that step waits its own delay, as if the reply went out now.
  let cumulativeDelay = 0;
  const materialized = steps.map((step) => {
    cumulativeDelay += step.delayMinutes;
    return {
      sequenceRunId: run.id,
      sequenceStepId: step.id,
      status: "scheduled" as const,
      dueAt: new Date(now.getTime() + cumulativeDelay * 60_000),
      expectedContextVersion: record.contextVersion,
    };
  });
  const stepRuns = await tx.insert(crmSequenceStepRuns).values(materialized).returning();

  await appendCrmEvent(tx, {
    personId: record.personId,
    crmRecordId: record.id,
    pipelineId: record.pipelineId,
    eventType: "sequence.started",
    actorType: input.actorType ?? (selection.source === "human_override" ? "authenticated_operator" : "ai"),
    actorRef: input.actorRef,
    fromData: existing ? { sequenceRunId: existing.id, status: "cancelled" } : null,
    toData: {
      sequenceRunId: run.id,
      sequenceId: run.sequenceId,
      sequenceVersionId: run.sequenceVersionId,
      startStepPosition: startPosition,
    },
    contextVersion: record.contextVersion,
  });
  return { run, stepRuns };
}

export function startSequenceRun(input: StartSequenceRunInput) {
  return withCrmTransaction((tx) => startSequenceRunInTransaction(tx, input));
}

/**
 * The record's latest reply is already answered, so its stage's sequence
 * starts at the first follow-up and the record waits for it to come due —
 * idle when the stage has no follow-ups (or no sequence) to send.
 */
export async function startFollowUpsInTransaction(
  tx: CrmTransaction,
  input: {
    recordId: string;
    conversationId: string;
    triggerMessageId: string;
    expectedContextVersion: number;
    actorType: "ai" | "authenticated_operator";
    actorRef?: string | null;
  },
) {
  const started = await startSequenceRunInTransaction(tx, { ...input, skipReply: true });
  const firstFollowUp = started?.stepRuns[0] ?? null;
  const [record] = await tx.update(crmRecords).set({
    workflowState: firstFollowUp ? "waiting" : "idle",
    nextActionAt: firstFollowUp?.dueAt ?? null,
    updatedAt: new Date(),
  }).where(eq(crmRecords.id, input.recordId)).returning();
  if (!record) throw new Error("CRM record update did not return a row");
  return { record, sequenceRun: started };
}

export async function setRecordSequenceOverride(input: {
  recordId: string;
  sequenceId: string | null;
  actorRef?: string | null;
}) {
  return withCrmTransaction(async (tx) => {
    const record = await lockCrmRecord(tx, input.recordId);
    const now = new Date();
    await tx
      .update(crmRecordSequenceOverrides)
      .set({ clearedAt: now, updatedAt: now })
      .where(and(
        eq(crmRecordSequenceOverrides.crmRecordId, record.id),
        isNull(crmRecordSequenceOverrides.clearedAt),
      ));
    let created = null;
    if (input.sequenceId) {
      const [sequence] = await tx
        .select()
        .from(crmSequences)
        .where(and(inOrg(crmSequences), eq(crmSequences.id, input.sequenceId)))
        .limit(1);
      if (!sequence) throw new CrmNotFoundError("CRM sequence", input.sequenceId);
      if (sequence.status !== "active" || !sequence.latestPublishedVersionId) {
        throw new CrmConflictError("Override sequence must be active and published");
      }
      [created] = await tx
        .insert(crmRecordSequenceOverrides)
        .values({
          crmRecordId: record.id,
          sequenceId: sequence.id,
          source: "human",
        })
        .returning();
    }
    await appendCrmEvent(tx, {
      personId: record.personId,
      crmRecordId: record.id,
      pipelineId: record.pipelineId,
      eventType: input.sequenceId ? "sequence.override_set" : "sequence.override_cleared",
      actorType: "authenticated_operator",
      actorRef: input.actorRef,
      toData: { sequenceId: input.sequenceId },
      contextVersion: record.contextVersion,
    });
    return created;
  });
}

export async function pauseSequence(input: { recordId: string; actorRef?: string | null }) {
  return withCrmTransaction(async (tx) => {
    const record = await lockCrmRecord(tx, input.recordId);
    const [run] = await tx.select().from(crmSequenceRuns)
      .where(and(eq(crmSequenceRuns.crmRecordId, record.id), eq(crmSequenceRuns.status, "active")))
      .limit(1).for("update");
    if (!run) throw new CrmConflictError("No active sequence run to pause");
    assertWorkflowTransition(record.workflowState, "paused");
    const nextContextVersion = record.contextVersion + 1;
    const now = new Date();
    const pending = await tx.select({ id: crmSequenceStepRuns.id, draftId: crmSequenceStepRuns.draftId })
      .from(crmSequenceStepRuns)
      .where(and(eq(crmSequenceStepRuns.sequenceRunId, run.id), inArray(crmSequenceStepRuns.status, ["drafting", "awaiting_review", "failed"])));
    const pendingDraftIds = pending.flatMap((step) => step.draftId ? [step.draftId] : []);
    if (pendingDraftIds.length) {
      await tx.update(crmDrafts).set({ status: "stale", updatedAt: now })
        .where(and(inArray(crmDrafts.id, pendingDraftIds), inArray(crmDrafts.status, ["generating", "awaiting_review", "failed"])));
      // The step forgets its draft below, so the draft must let go of the step
      // too, or the step's next draft collides with it in crm_drafts_step_run_uq.
      await tx.update(crmDrafts).set({ sequenceStepRunId: null })
        .where(inArray(crmDrafts.id, pendingDraftIds));
      await tx.update(crmSequenceStepRuns).set({ status: "scheduled", draftId: null, expectedContextVersion: nextContextVersion, updatedAt: now })
        .where(inArray(crmSequenceStepRuns.id, pending.map((step) => step.id)));
    }
    const [updatedRun] = await tx.update(crmSequenceRuns).set({ status: "paused", updatedAt: now })
      .where(eq(crmSequenceRuns.id, run.id)).returning();
    await tx.update(crmRecords).set({ workflowState: "paused", nextActionAt: null, contextVersion: nextContextVersion, updatedAt: now })
      .where(eq(crmRecords.id, record.id));
    await appendCrmEvent(tx, {
      personId: record.personId, crmRecordId: record.id, pipelineId: record.pipelineId,
      eventType: "sequence.paused", actorType: "authenticated_operator", actorRef: input.actorRef,
      fromData: { workflowState: record.workflowState }, toData: { workflowState: "paused", sequenceRunId: run.id },
      contextVersion: nextContextVersion,
    });
    return updatedRun!;
  });
}

export async function resumeSequence(input: { recordId: string; actorRef?: string | null }) {
  return withCrmTransaction(async (tx) => {
    const record = await lockCrmRecord(tx, input.recordId);
    const [run] = await tx.select().from(crmSequenceRuns)
      .where(and(eq(crmSequenceRuns.crmRecordId, record.id), eq(crmSequenceRuns.status, "paused")))
      .orderBy(sql`${crmSequenceRuns.updatedAt} DESC`).limit(1).for("update");
    if (!run) throw new CrmConflictError("No paused sequence run to resume");
    assertWorkflowTransition(record.workflowState, "waiting");
    const [nextStep] = await tx.select().from(crmSequenceStepRuns)
      .where(and(eq(crmSequenceStepRuns.sequenceRunId, run.id), inArray(crmSequenceStepRuns.status, ["scheduled", "awaiting_review", "failed"])))
      .orderBy(asc(crmSequenceStepRuns.dueAt)).limit(1);
    const workflowState = nextStep?.status === "awaiting_review" || nextStep?.status === "failed"
      ? "action_required" as const
      : "waiting" as const;
    assertWorkflowTransition(record.workflowState, workflowState);
    const nextContextVersion = record.contextVersion + 1;
    const now = new Date();
    const [updatedRun] = await tx.update(crmSequenceRuns).set({ status: "active", updatedAt: now })
      .where(eq(crmSequenceRuns.id, run.id)).returning();
    await tx.update(crmRecords).set({ workflowState, nextActionAt: nextStep?.dueAt ?? null, contextVersion: nextContextVersion, updatedAt: now })
      .where(eq(crmRecords.id, record.id));
    await tx.update(crmSequenceStepRuns).set({ expectedContextVersion: nextContextVersion, updatedAt: now })
      .where(and(eq(crmSequenceStepRuns.sequenceRunId, run.id), inArray(crmSequenceStepRuns.status, ["scheduled", "awaiting_review", "failed"])));
    await appendCrmEvent(tx, {
      personId: record.personId, crmRecordId: record.id, pipelineId: record.pipelineId,
      eventType: "sequence.resumed", actorType: "authenticated_operator", actorRef: input.actorRef,
      fromData: { workflowState: record.workflowState }, toData: { workflowState, sequenceRunId: run.id },
      contextVersion: nextContextVersion,
    });
    return updatedRun!;
  });
}

/**
 * After an action that bumps the record's context version but keeps its run
 * (skip, snooze), every step still to come must carry the new version: a
 * step is drafted only when its version matches the record's
 * (loadDraftContext). Updating only the next step left the ones after it on
 * the old version, so once the next step was sent the run advanced onto a
 * step that could never be drafted, and the record waited forever with
 * nothing on anyone's desk.
 */
export async function refreshPendingStepContextInTransaction(
  tx: CrmTransaction,
  runId: string,
  contextVersion: number,
  now: Date = new Date(),
): Promise<void> {
  await tx.update(crmSequenceStepRuns).set({ expectedContextVersion: contextVersion, updatedAt: now })
    .where(and(
      eq(crmSequenceStepRuns.sequenceRunId, runId),
      inArray(crmSequenceStepRuns.status, ["scheduled", "awaiting_review", "failed"]),
    ));
}

export async function snoozeSequence(input: { recordId: string; until: Date; actorRef?: string | null }) {
  if (!(input.until instanceof Date) || Number.isNaN(input.until.getTime()) || input.until <= new Date()) {
    throw new Error("Snooze time must be a valid future date");
  }
  return withCrmTransaction(async (tx) => {
    const record = await lockCrmRecord(tx, input.recordId);
    const [run] = await tx.select().from(crmSequenceRuns)
      .where(and(eq(crmSequenceRuns.crmRecordId, record.id), eq(crmSequenceRuns.status, "active")))
      .limit(1).for("update");
    if (!run) throw new CrmConflictError("No active sequence run to snooze");
    const [step] = await tx.select().from(crmSequenceStepRuns)
      .where(and(eq(crmSequenceStepRuns.sequenceRunId, run.id), inArray(crmSequenceStepRuns.status, ["scheduled", "awaiting_review", "failed"])))
      .orderBy(asc(crmSequenceStepRuns.dueAt)).limit(1);
    if (!step) throw new CrmConflictError("No pending sequence step to snooze");
    assertWorkflowTransition(record.workflowState, "waiting");
    const nextContextVersion = record.contextVersion + 1;
    const now = new Date();
    await refreshPendingStepContextInTransaction(tx, run.id, nextContextVersion, now);
    await tx.update(crmSequenceStepRuns).set({ dueAt: input.until, updatedAt: now })
      .where(eq(crmSequenceStepRuns.id, step.id));
    const [updated] = await tx.update(crmRecords)
      .set({ workflowState: "waiting", nextActionAt: input.until, contextVersion: nextContextVersion, updatedAt: now })
      .where(eq(crmRecords.id, record.id)).returning();
    await appendCrmEvent(tx, {
      personId: record.personId, crmRecordId: record.id, pipelineId: record.pipelineId,
      eventType: "sequence.snoozed", actorType: "authenticated_operator", actorRef: input.actorRef,
      fromData: { dueAt: step.dueAt }, toData: { dueAt: input.until.toISOString(), stepRunId: step.id },
      contextVersion: nextContextVersion,
    });
    return updated!;
  });
}

export async function skipCurrentSequenceStep(input: { recordId: string; actorRef?: string | null }) {
  return withCrmTransaction(async (tx) => {
    const record = await lockCrmRecord(tx, input.recordId);
    const [run] = await tx.select().from(crmSequenceRuns)
      .where(and(eq(crmSequenceRuns.crmRecordId, record.id), eq(crmSequenceRuns.status, "active")))
      .limit(1).for("update");
    if (!run) throw new CrmConflictError("No active sequence run");
    const candidates = await tx.select({ stepRun: crmSequenceStepRuns, step: crmSequenceSteps })
      .from(crmSequenceStepRuns)
      .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
      .where(and(eq(crmSequenceStepRuns.sequenceRunId, run.id), inArray(crmSequenceStepRuns.status, ["scheduled", "awaiting_review", "failed"])))
      .orderBy(asc(crmSequenceSteps.position));
    const current = candidates[0];
    if (!current) throw new CrmConflictError("No pending sequence step");
    const now = new Date();
    if (current.stepRun.draftId) {
      await tx.update(crmDrafts).set({ status: "discarded", updatedAt: now })
        .where(and(eq(crmDrafts.id, current.stepRun.draftId), inArray(crmDrafts.status, ["generating", "awaiting_review", "failed"])));
    }
    await tx.update(crmSequenceStepRuns).set({ status: "skipped", updatedAt: now })
      .where(eq(crmSequenceStepRuns.id, current.stepRun.id));
    const next = candidates[1];
    const nextContextVersion = record.contextVersion + 1;
    await refreshPendingStepContextInTransaction(tx, run.id, nextContextVersion, now);
    if (next) {
      // Skipping means "this step is handled", so the next one waits its own
      // delay from now — the same clock a send starts — rather than coming
      // due at once and drafting a follow-up on the heels of the skip.
      const dueAt = new Date(now.getTime() + next.step.delayMinutes * 60_000);
      await tx.update(crmSequenceStepRuns).set({ dueAt, updatedAt: now })
        .where(eq(crmSequenceStepRuns.id, next.stepRun.id));
      await tx.update(crmSequenceRuns).set({ currentStepPosition: next.step.position, updatedAt: now })
        .where(eq(crmSequenceRuns.id, run.id));
      await tx.update(crmRecords).set({ workflowState: "waiting", nextActionAt: dueAt, contextVersion: nextContextVersion, updatedAt: now })
        .where(eq(crmRecords.id, record.id));
    } else {
      await tx.update(crmSequenceRuns).set({ status: "completed", updatedAt: now })
        .where(eq(crmSequenceRuns.id, run.id));
      await tx.update(crmRecords).set({ workflowState: "idle", nextActionAt: null, contextVersion: nextContextVersion, updatedAt: now })
        .where(eq(crmRecords.id, record.id));
    }
    await appendCrmEvent(tx, {
      personId: record.personId, crmRecordId: record.id, pipelineId: record.pipelineId,
      eventType: "sequence.step_skipped", actorType: "authenticated_operator", actorRef: input.actorRef,
      fromData: { stepRunId: current.stepRun.id, position: current.step.position },
      toData: next ? { stepRunId: next.stepRun.id, position: next.step.position } : { sequenceCompleted: true },
      contextVersion: nextContextVersion,
    });
    return { skipped: current.stepRun.id, next: next?.stepRun.id ?? null };
  });
}

export async function enqueueDueFollowupJobs(limit = 100): Promise<number> {
  const safeLimit = Math.max(1, Math.min(500, Math.floor(limit)));
  return withCrmTransaction(async (tx) => {
    // A global sweep: it runs in no organization, so each row brings its own
    // into the job it enqueues.
    const rows = await tx.select({ stepRunId: crmSequenceStepRuns.id, organizationId: crmSequenceRuns.organizationId })
      .from(crmSequenceStepRuns)
      .innerJoin(crmSequenceRuns, eq(crmSequenceRuns.id, crmSequenceStepRuns.sequenceRunId))
      .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
      .where(and(
        eq(crmSequenceRuns.status, "active"),
        eq(crmSequenceStepRuns.status, "scheduled"),
        eq(crmSequenceSteps.stepType, "follow_up"),
        // Only the run's current step. currentStepPosition advances when the
        // previous step is sent or skipped, so this is what stops a follow-up
        // from being drafted while the reply it follows is still unsent —
        // every step's dueAt is set at run start, and before this gate the
        // clock alone made 18 follow-ups come due under unsent replies.
        eq(crmSequenceSteps.position, crmSequenceRuns.currentStepPosition),
        sql`${crmSequenceStepRuns.dueAt} <= now()`,
      ))
      .orderBy(asc(crmSequenceStepRuns.dueAt))
      .limit(safeLimit)
      .for("update", { skipLocked: true });
    if (!rows.length) return 0;
    const { enqueueCrmJobInTransaction } = await import("./queue");
    for (const row of rows) {
      await enqueueCrmJobInTransaction(tx, {
        kind: "due_followup_draft",
        entityId: row.stepRunId,
        idempotencyKey: `crm:due-followup:${row.stepRunId}`,
        organizationId: row.organizationId,
      });
    }
    return rows.length;
  });
}

// Configuration lifecycle --------------------------------------------------

export type SequenceStepInput = {
  name: string;
  delayMinutes: number;
  subjectTemplate: string | null;
  bodyTemplate: string | null;
  aiInstructions: string;
  knowledgeTags: string[];
};

function configStatus(value: unknown): CrmSequenceStatus {
  if (value !== "active" && value !== "archived") {
    throw new CrmConfigurationValidationError("status must be active or archived");
  }
  return value;
}

function stepDelay(value: unknown, position: number): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new CrmConfigurationValidationError(`steps[${position - 1}].delayMinutes must be a non-negative integer`);
  }
  if (position === 1 && value !== 0) throw new CrmConfigurationValidationError("Step 1 must have zero delay");
  if (position > 1 && value === 0) throw new CrmConfigurationValidationError("Follow-up steps must have a positive delay");
  return value;
}

function configTags(value: unknown, label: string): string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > 50) {
    throw new CrmConfigurationValidationError(`${label} must be an array with at most 50 values`);
  }
  const tags = value.map((tag, index) => parseRequiredText(tag, `${label}[${index}]`, 80).toLowerCase());
  if (new Set(tags).size !== tags.length) throw new CrmConfigurationValidationError(`${label} cannot contain duplicates`);
  return tags;
}

export function parseSequenceSteps(value: unknown): SequenceStepInput[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > 30) {
    throw new CrmConfigurationValidationError("steps must be an array with at most 30 items");
  }
  return value.map((raw, index) => {
    assertObject(raw, `steps[${index}]`);
    assertExactKeys(raw, ["name", "delayMinutes", "subjectTemplate", "bodyTemplate", "aiInstructions", "knowledgeTags"]);
    const subjectTemplate = parseOptionalText(raw.subjectTemplate, `steps[${index}].subjectTemplate`, 500) ?? null;
    return {
      name: parseRequiredText(raw.name, `steps[${index}].name`, 120),
      delayMinutes: stepDelay(raw.delayMinutes, index + 1),
      subjectTemplate,
      bodyTemplate: parseOptionalText(raw.bodyTemplate, `steps[${index}].bodyTemplate`, 20_000) ?? null,
      aiInstructions: parseRequiredText(raw.aiInstructions, `steps[${index}].aiInstructions`, 8_000),
      knowledgeTags: configTags(raw.knowledgeTags, `steps[${index}].knowledgeTags`),
    };
  });
}

export function validatePublishableSteps(steps: readonly SequenceStepInput[]): void {
  if (!steps.length) throw new CrmConflictError("A sequence needs an immediate reply step before publishing");
  steps.forEach((step, index) => {
    stepDelay(step.delayMinutes, index + 1);
  });
}

export function parseCreateSequenceInput(value: unknown) {
  assertObject(value);
  assertExactKeys(value, ["name", "description", "steps"]);
  return {
    name: parseRequiredText(value.name, "name", 160),
    description: parseOptionalText(value.description, "description", 4_000) ?? null,
    steps: parseSequenceSteps(value.steps),
  };
}

function configStepRows(versionId: string, steps: readonly SequenceStepInput[]) {
  return steps.map((step, index) => ({
    sequenceVersionId: versionId,
    position: index + 1,
    stepType: index === 0 ? "reply" as const : "follow_up" as const,
    ...step,
  }));
}

export async function createSequence(value: unknown) {
  const input = parseCreateSequenceInput(value);
  return withCrmTransaction(async (tx) => {
    const sequenceId = randomUUID();
    const draftVersionId = randomUUID();
    const [sequence] = await tx.insert(crmSequences).values({
      organizationId: currentOrganizationId(),
      id: sequenceId,
      name: input.name,
      description: input.description,
      draftVersionId,
    }).returning();
    if (!sequence) throw new Error("CRM sequence insert did not return a row");
    await tx.insert(crmSequenceVersions).values({ id: draftVersionId, sequenceId, version: 1, status: "draft" });
    if (input.steps.length) await tx.insert(crmSequenceSteps).values(configStepRows(draftVersionId, input.steps));
    return { ...sequence, draftVersion: 1, steps: input.steps };
  });
}

export async function listSequences(input: { includeArchived?: boolean }) {
  const sequences = await db.select().from(crmSequences).where(and(
    inOrg(crmSequences),
    input.includeArchived ? undefined : eq(crmSequences.status, "active"),
  )).orderBy(asc(crmSequences.name));
  if (!sequences.length) return [];
  // One batch per table, not four queries per sequence: at ~170 ms a round
  // trip through an 8-connection pool, the per-sequence version took over
  // four seconds to list a few dozen sequences.
  const sequenceIds = sequences.map((sequence) => sequence.id);
  const draftVersionIds = sequences.map((sequence) => sequence.draftVersionId);
  const versionIds = [...new Set([...draftVersionIds, ...sequences.flatMap((sequence) => sequence.latestPublishedVersionId ? [sequence.latestPublishedVersionId] : [])])];
  const [versions, stepCounts, assignments] = await Promise.all([
    db.select({ id: crmSequenceVersions.id, version: crmSequenceVersions.version }).from(crmSequenceVersions)
      .where(inArray(crmSequenceVersions.id, versionIds)),
    db.select({ sequenceVersionId: crmSequenceSteps.sequenceVersionId, steps: count() }).from(crmSequenceSteps)
      .where(inArray(crmSequenceSteps.sequenceVersionId, draftVersionIds))
      .groupBy(crmSequenceSteps.sequenceVersionId),
    db.select({ sequenceId: crmSubcategorySequenceAssignments.sequenceId, subcategoryId: crmSubcategorySequenceAssignments.subcategoryId })
      .from(crmSubcategorySequenceAssignments)
      .where(inArray(crmSubcategorySequenceAssignments.sequenceId, sequenceIds)),
  ]);
  const versionNumber = new Map(versions.map((row) => [row.id, row.version]));
  const stepCount = new Map(stepCounts.map((row) => [row.sequenceVersionId, Number(row.steps)]));
  return sequences.map((sequence) => ({
    ...sequence,
    draftVersion: versionNumber.get(sequence.draftVersionId) ?? null,
    latestPublishedVersion: sequence.latestPublishedVersionId ? versionNumber.get(sequence.latestPublishedVersionId) ?? null : null,
    draftStepCount: stepCount.get(sequence.draftVersionId) ?? 0,
    assignedSubcategoryIds: assignments.filter((assignment) => assignment.sequenceId === sequence.id).map((assignment) => assignment.subcategoryId),
  }));
}

export async function getSequence(id: string) {
  parseUuid(id, "sequence id");
  const [sequence] = await db.select().from(crmSequences)
    .where(and(inOrg(crmSequences), eq(crmSequences.id, id))).limit(1);
  if (!sequence) throw new CrmNotFoundError("CRM sequence", id);
  const [versions, draftSteps, assignments] = await Promise.all([
    db.select().from(crmSequenceVersions).where(eq(crmSequenceVersions.sequenceId, id)).orderBy(asc(crmSequenceVersions.version)),
    db.select().from(crmSequenceSteps).where(eq(crmSequenceSteps.sequenceVersionId, sequence.draftVersionId)).orderBy(asc(crmSequenceSteps.position)),
    db.select().from(crmSubcategorySequenceAssignments).where(eq(crmSubcategorySequenceAssignments.sequenceId, id)),
  ]);
  return { ...sequence, versions, draftSteps, assignments };
}

export function parseUpdateSequenceInput(value: unknown): {
  name?: string;
  description?: string | null;
  status?: CrmSequenceStatus;
  autoSendFollowUps?: boolean;
  steps?: SequenceStepInput[];
} {
  assertObject(value);
  assertExactKeys(value, ["name", "description", "status", "autoSendFollowUps", "steps"]);
  const parsed: {
    name?: string;
    description?: string | null;
    status?: CrmSequenceStatus;
    autoSendFollowUps?: boolean;
    steps?: SequenceStepInput[];
  } = {};
  if (value.name !== undefined) parsed.name = parseRequiredText(value.name, "name", 160);
  if (value.autoSendFollowUps !== undefined) {
    if (typeof value.autoSendFollowUps !== "boolean") {
      throw new CrmConfigurationValidationError("autoSendFollowUps must be true or false");
    }
    parsed.autoSendFollowUps = value.autoSendFollowUps;
  }
  if (value.description !== undefined) parsed.description = parseOptionalText(value.description, "description", 4_000) ?? null;
  if (value.status !== undefined) parsed.status = configStatus(value.status);
  if (value.steps !== undefined) parsed.steps = parseSequenceSteps(value.steps);
  if (!Object.keys(parsed).length) throw new CrmConfigurationValidationError("At least one editable field is required");
  return parsed;
}

export async function updateSequence(id: string, value: unknown) {
  parseUuid(id, "sequence id");
  return withCrmTransaction(async (tx) => {
    const [sequence] = await tx.select().from(crmSequences)
      .where(and(inOrg(crmSequences), eq(crmSequences.id, id))).limit(1).for("update");
    if (!sequence) throw new CrmNotFoundError("CRM sequence", id);
    const input = parseUpdateSequenceInput(value);
    const { steps, ...metadata } = input;
    let updated = sequence;
    if (Object.keys(metadata).length) {
      const [row] = await tx.update(crmSequences).set({ ...metadata, updatedAt: new Date() })
        .where(and(inOrg(crmSequences), eq(crmSequences.id, id))).returning();
      if (!row) throw new Error("CRM sequence update did not return a row");
      updated = row;
    }
    if (sequence.autoSendFollowUps && metadata.autoSendFollowUps === false) {
      // Switched off: follow-ups already drafted for the sender become
      // ordinary drafts for a person to review. (Imported here: autoFollowUps
      // reaches this module through send.ts.)
      const { handSequenceAutoFollowUpsToRepInTransaction } = await import("./autoFollowUps");
      await handSequenceAutoFollowUpsToRepInTransaction(tx, { sequenceId: id });
    }
    if (steps !== undefined) {
      const [draft] = await tx.select().from(crmSequenceVersions).where(and(
        eq(crmSequenceVersions.id, sequence.draftVersionId),
        eq(crmSequenceVersions.status, "draft"),
      )).limit(1).for("update");
      if (!draft) throw new CrmConflictError("The current sequence version is not editable");
      await tx.delete(crmSequenceSteps).where(eq(crmSequenceSteps.sequenceVersionId, draft.id));
      if (steps.length) await tx.insert(crmSequenceSteps).values(configStepRows(draft.id, steps));
    }
    return updated;
  });
}

/**
 * Permanently remove a sequence that has never participated in CRM history.
 * Default subcategory assignments are configuration, so they are detached as
 * part of deletion. Runs and record overrides are durable history and block it.
 */
export async function deleteSequence(id: string) {
  parseUuid(id, "sequence id");
  return withCrmTransaction(async (tx) => {
    const [sequence] = await tx.select().from(crmSequences)
      .where(and(inOrg(crmSequences), eq(crmSequences.id, id))).limit(1).for("update");
    if (!sequence) throw new CrmNotFoundError("CRM sequence", id);

    const [run] = await tx.select({ id: crmSequenceRuns.id }).from(crmSequenceRuns)
      .where(eq(crmSequenceRuns.sequenceId, id)).limit(1);
    if (run) {
      throw new CrmConflictError("This sequence has CRM activity history and cannot be permanently deleted");
    }

    const [override] = await tx.select({ id: crmRecordSequenceOverrides.id }).from(crmRecordSequenceOverrides)
      .where(eq(crmRecordSequenceOverrides.sequenceId, id)).limit(1);
    if (override) {
      throw new CrmConflictError("This sequence has record assignment history and cannot be permanently deleted");
    }

    const removedAssignments = await tx.delete(crmSubcategorySequenceAssignments)
      .where(eq(crmSubcategorySequenceAssignments.sequenceId, id))
      .returning({ subcategoryId: crmSubcategorySequenceAssignments.subcategoryId });
    const versions = await tx.select({ id: crmSequenceVersions.id }).from(crmSequenceVersions)
      .where(eq(crmSequenceVersions.sequenceId, id));
    const versionIds = versions.map((version) => version.id);
    if (versionIds.length) {
      await tx.delete(crmSequenceSteps).where(inArray(crmSequenceSteps.sequenceVersionId, versionIds));
    }
    // Sequence and version rows reference each other. Removing both in one
    // statement satisfies the immediate version-to-sequence foreign key while
    // the deferrable sequence-to-version pointers are checked at commit.
    await tx.execute(sql`
      WITH deleted_sequence AS (
        DELETE FROM ${crmSequences}
        WHERE ${crmSequences.id} = ${id}
          AND ${crmSequences.organizationId} = ${currentOrganizationId()}
        RETURNING ${crmSequences.id}
      )
      DELETE FROM ${crmSequenceVersions}
      WHERE ${crmSequenceVersions.sequenceId} IN (SELECT id FROM deleted_sequence)
    `);
    return { id, removedAssignmentCount: removedAssignments.length };
  });
}

export async function publishSequence(id: string) {
  parseUuid(id, "sequence id");
  return withCrmTransaction(async (tx) => {
    const [sequence] = await tx.select().from(crmSequences)
      .where(and(inOrg(crmSequences), eq(crmSequences.id, id))).limit(1).for("update");
    if (!sequence) throw new CrmNotFoundError("CRM sequence", id);
    if (sequence.status !== "active") throw new CrmConflictError("Archived sequences cannot be published");
    const [draft] = await tx.select().from(crmSequenceVersions).where(and(
      eq(crmSequenceVersions.id, sequence.draftVersionId),
      eq(crmSequenceVersions.status, "draft"),
    )).limit(1).for("update");
    if (!draft) throw new CrmConflictError("The sequence has no mutable draft version");
    const steps = await tx.select().from(crmSequenceSteps)
      .where(eq(crmSequenceSteps.sequenceVersionId, draft.id)).orderBy(asc(crmSequenceSteps.position));
    validatePublishableSteps(steps);
    const now = new Date();
    await tx.update(crmSequenceVersions).set({ status: "published", publishedAt: now, updatedAt: now })
      .where(eq(crmSequenceVersions.id, draft.id));
    const nextDraftId = randomUUID();
    const [nextDraft] = await tx.insert(crmSequenceVersions)
      .values({ id: nextDraftId, sequenceId: id, version: draft.version + 1, status: "draft" }).returning();
    if (!nextDraft) throw new Error("Next CRM sequence draft insert did not return a row");
    await tx.insert(crmSequenceSteps).values(steps.map((step) => ({
      sequenceVersionId: nextDraftId,
      position: step.position,
      stepType: step.stepType,
      name: step.name,
      delayMinutes: step.delayMinutes,
      subjectTemplate: step.subjectTemplate,
      bodyTemplate: step.bodyTemplate,
      aiInstructions: step.aiInstructions,
      knowledgeTags: step.knowledgeTags,
    })));
    const [updated] = await tx.update(crmSequences).set({
      draftVersionId: nextDraftId,
      latestPublishedVersionId: draft.id,
      updatedAt: now,
    }).where(and(inOrg(crmSequences), eq(crmSequences.id, id))).returning();
    if (!updated) throw new Error("Published CRM sequence update did not return a row");
    return { sequence: updated, publishedVersion: draft.version, nextDraftVersion: nextDraft.version };
  });
}

export function parseAssignmentInput(value: unknown): { sequenceId: string | null } {
  assertObject(value);
  assertExactKeys(value, ["sequenceId"]);
  return { sequenceId: value.sequenceId === null ? null : parseUuid(value.sequenceId, "sequenceId") };
}

export async function assignSubcategorySequence(subcategoryId: string, value: unknown) {
  parseUuid(subcategoryId, "subcategory id");
  const { sequenceId } = parseAssignmentInput(value);
  return withCrmTransaction(async (tx) => {
    const [subcategory] = await tx.select().from(crmSubcategories)
      .where(and(
        inArray(crmSubcategories.pipelineId, tx.select({ id: crmPipelines.id }).from(crmPipelines).where(inOrg(crmPipelines))),
        eq(crmSubcategories.id, subcategoryId),
      )).limit(1);
    if (!subcategory) throw new CrmNotFoundError("CRM subcategory", subcategoryId);
    if (!subcategory.active) throw new CrmConflictError("Archived subcategories cannot receive new sequence assignments");
    if (sequenceId === null) {
      await tx.delete(crmSubcategorySequenceAssignments)
        .where(eq(crmSubcategorySequenceAssignments.subcategoryId, subcategoryId));
      return { subcategoryId, sequenceId: null };
    }
    const [sequence] = await tx.select().from(crmSequences)
      .where(and(inOrg(crmSequences), eq(crmSequences.id, sequenceId))).limit(1);
    if (!sequence) throw new CrmNotFoundError("CRM sequence", sequenceId);
    if (sequence.status !== "active" || !sequence.latestPublishedVersionId) {
      throw new CrmConflictError("Only active published sequences can be assigned");
    }
    const [assignment] = await tx.insert(crmSubcategorySequenceAssignments)
      .values({ subcategoryId, sequenceId })
      .onConflictDoUpdate({
        target: [crmSubcategorySequenceAssignments.subcategoryId],
        set: { sequenceId, updatedAt: new Date() },
      }).returning();
    if (!assignment) throw new Error("CRM sequence assignment did not return a row");
    return assignment;
  });
}
