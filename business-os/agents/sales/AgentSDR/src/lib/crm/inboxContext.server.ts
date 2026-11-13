/**
 * Record-level readers behind ./inboxContext — what any inbox shows once it
 * has mapped its own thread to a CRM conversation. Channel lookups stay with
 * the inbox that owns them (src/lib/linkedin/messages/crmContext.server,
 * src/lib/inbox/crmContext.server); this module never touches a thread table.
 *
 * Kept apart from ./inboxContext so the client-safe module never pulls the
 * postgres driver into the browser bundle.
 */
import { and, desc, eq, inArray, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { isPersonDoNotContact } from "./policies";
import { inOrg } from "@/lib/tenancy/scope";
import {
  crmClassifications,
  crmDrafts,
  crmRecords,
  crmSequenceRuns,
  crmSequenceStepRuns,
  crmSequenceSteps,
  crmSequences,
  crmSubcategories,
} from "./schema";
import type { InboxCrmContext, InboxCrmDraft, InboxCrmStep, InboxCrmSummary } from "./inboxContext";

/** The CRM conversation an inbox thread resolved to. */
export type InboxCrmConversationScope = {
  id: string;
  recordId: string;
  personId: string;
};

const PENDING_STEP_STATUSES = ["scheduled", "drafting", "awaiting_review", "failed"] as const;
const OPEN_DRAFT_STATUSES = ["generating", "awaiting_review", "failed"] as const;

type RecordHead = {
  recordId: string;
  workflowState: InboxCrmSummary["workflowState"];
  categoryKey: string | null;
  subcategoryId: string | null;
  subcategoryName: string | null;
  nextActionAt: Date | null;
};

type RecordProgress = {
  sequenceName: string | null;
  step: InboxCrmStep | null;
  hasDraft: boolean;
};

const recordHeadSelection = {
  recordId: crmRecords.id,
  workflowState: crmRecords.workflowState,
  categoryKey: crmRecords.categoryKey,
  subcategoryId: crmRecords.subcategoryId,
  subcategoryName: crmSubcategories.name,
  nextActionAt: crmRecords.nextActionAt,
};

/**
 * Sequence position and open-draft flag for a set of records, in two queries.
 * The step is the active run's earliest step run still to be sent; `total`
 * counts the steps of the version that run is pinned to.
 */
async function loadRecordProgress(recordIds: string[]): Promise<Map<string, RecordProgress>> {
  const progress = new Map<string, RecordProgress>();
  if (recordIds.length === 0) return progress;

  const [runRows, draftRows] = await Promise.all([
    db
      .select({
        recordId: crmSequenceRuns.crmRecordId,
        sequenceName: crmSequences.name,
        total: sql<number>`(
          SELECT COUNT(*)::int FROM ${crmSequenceSteps} s
          WHERE s.sequence_version_id = ${crmSequenceRuns.sequenceVersionId}
        )`,
        stepStatus: crmSequenceStepRuns.status,
        dueAt: crmSequenceStepRuns.dueAt,
        position: crmSequenceSteps.position,
        stepName: crmSequenceSteps.name,
        stepType: crmSequenceSteps.stepType,
      })
      .from(crmSequenceRuns)
      .innerJoin(crmSequences, eq(crmSequences.id, crmSequenceRuns.sequenceId))
      .leftJoin(
        crmSequenceStepRuns,
        and(
          eq(crmSequenceStepRuns.sequenceRunId, crmSequenceRuns.id),
          inArray(crmSequenceStepRuns.status, [...PENDING_STEP_STATUSES]),
        ),
      )
      .leftJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
      .where(and(inOrg(crmSequenceRuns), inArray(crmSequenceRuns.crmRecordId, recordIds), eq(crmSequenceRuns.status, "active")))
      .orderBy(
        crmSequenceRuns.crmRecordId,
        desc(crmSequenceRuns.createdAt),
        crmSequenceRuns.id,
        sql`${crmSequenceSteps.position} ASC NULLS LAST`,
      ),
    db
      .selectDistinct({ recordId: crmDrafts.crmRecordId })
      .from(crmDrafts)
      .where(and(inArray(crmDrafts.crmRecordId, recordIds), eq(crmDrafts.status, "awaiting_review"))),
  ]);

  const hasDraft = new Set(draftRows.map((row) => row.recordId));
  for (const row of runRows) {
    if (progress.has(row.recordId)) continue;
    const step: InboxCrmStep | null =
      row.position !== null && row.stepStatus !== null
        ? {
            position: row.position,
            total: Number(row.total),
            name: row.stepName ?? "",
            type: row.stepType ?? "follow_up",
            status: row.stepStatus as InboxCrmStep["status"],
            dueAt: row.dueAt?.toISOString() ?? null,
          }
        : null;
    progress.set(row.recordId, { sequenceName: row.sequenceName, step, hasDraft: hasDraft.has(row.recordId) });
  }
  for (const recordId of recordIds) {
    if (!progress.has(recordId)) {
      progress.set(recordId, { sequenceName: null, step: null, hasDraft: hasDraft.has(recordId) });
    }
  }
  return progress;
}

function toSummary(head: RecordHead, progress: RecordProgress): InboxCrmSummary {
  return {
    recordId: head.recordId,
    workflowState: head.workflowState,
    categoryKey: head.categoryKey,
    subcategoryId: head.subcategoryId,
    subcategoryName: head.subcategoryName,
    nextActionAt: head.nextActionAt?.toISOString() ?? null,
    sequenceName: progress.sequenceName,
    step: progress.step,
    hasDraft: progress.hasDraft,
  };
}

/**
 * List-row summaries for a set of CRM records, keyed by record id. Batched:
 * one head query and the two progress queries, never a query per row.
 * Records that do not exist are simply absent from the map.
 */
export async function loadInboxCrmSummariesForRecords(recordIds: string[]): Promise<Map<string, InboxCrmSummary>> {
  const summaries = new Map<string, InboxCrmSummary>();
  const ids = [...new Set(recordIds)];
  if (ids.length === 0) return summaries;

  const [heads, progress] = await Promise.all([
    db
      .select(recordHeadSelection)
      .from(crmRecords)
      .leftJoin(crmSubcategories, eq(crmSubcategories.id, crmRecords.subcategoryId))
      .where(and(inOrg(crmRecords), inArray(crmRecords.id, ids))),
    loadRecordProgress(ids),
  ]);
  for (const head of heads) {
    summaries.set(head.recordId, toSummary(head, progress.get(head.recordId)!));
  }
  return summaries;
}

/**
 * Everything the open thread's CRM strip needs for a resolved conversation;
 * null only if the record vanished between the lookup and this read.
 */
export async function loadInboxCrmContextForConversation(
  scope: InboxCrmConversationScope,
): Promise<InboxCrmContext | null> {
  const [[head], progress, [draftRow], [classification], doNotContact] = await Promise.all([
    db
      .select({ ...recordHeadSelection, contextVersion: crmRecords.contextVersion })
      .from(crmRecords)
      .leftJoin(crmSubcategories, eq(crmSubcategories.id, crmRecords.subcategoryId))
      .where(and(inOrg(crmRecords), eq(crmRecords.id, scope.recordId)))
      .limit(1),
    loadRecordProgress([scope.recordId]),
    db
      .select({
        id: crmDrafts.id,
        revision: crmDrafts.revision,
        status: crmDrafts.status,
        subject: crmDrafts.subject,
        aiBodyText: crmDrafts.aiBodyText,
        editedBodyText: crmDrafts.editedBodyText,
        error: crmDrafts.error,
        stepType: crmSequenceSteps.stepType,
        stepName: crmSequenceSteps.name,
      })
      .from(crmDrafts)
      .leftJoin(crmSequenceStepRuns, eq(crmSequenceStepRuns.id, crmDrafts.sequenceStepRunId))
      .leftJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
      .where(and(eq(crmDrafts.crmRecordId, scope.recordId), inArray(crmDrafts.status, [...OPEN_DRAFT_STATUSES])))
      .orderBy(desc(crmDrafts.updatedAt))
      .limit(1),
    db
      .select({ id: crmClassifications.id })
      .from(crmClassifications)
      .where(eq(crmClassifications.crmRecordId, scope.recordId))
      .orderBy(desc(crmClassifications.createdAt))
      .limit(1),
    isPersonDoNotContact(db, scope.personId),
  ]);
  if (!head) return null;

  const draft: InboxCrmDraft | null = draftRow
    ? {
        id: draftRow.id,
        revision: draftRow.revision,
        status: draftRow.status as InboxCrmDraft["status"],
        subject: draftRow.subject,
        body: draftRow.editedBodyText ?? draftRow.aiBodyText ?? "",
        stepType: draftRow.stepType ?? null,
        stepName: draftRow.stepName ?? null,
        error: draftRow.error,
      }
    : null;

  return {
    ...toSummary(head, progress.get(scope.recordId)!),
    conversationId: scope.id,
    contextVersion: head.contextVersion,
    doNotContact,
    classificationId: classification?.id ?? null,
    draft,
  };
}
