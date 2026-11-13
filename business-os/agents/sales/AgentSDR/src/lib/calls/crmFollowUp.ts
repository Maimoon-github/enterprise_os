import "server-only";

import { and, eq, isNotNull, isNull, min, ne } from "drizzle-orm";
import { db } from "@/lib/db";
import { appendCrmEvent } from "@/lib/crm/events";
import { withCrmTransaction } from "@/lib/crm/repository";
import { crmRecords, type CrmRecordChannel, type CrmWorkflowState } from "@/lib/crm/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { lockOrCreateRecord, lockRepresentativeRecord } from "./leadStage";
import { callCampaignContacts, callCampaigns, callSessions } from "./schema";

/**
 * A called lead's next follow-up, mirrored onto their CRM record so it shows
 * in Action required once due — like a sequence's follow-up does, with
 * "whatsapp" as the record's channel.
 *
 * Only for leads the rep has spoken to (a recorded call) or who already have
 * a CRM record; retries for people who never picked up stay in the
 * campaign's Due today tab. And only for call-only records: a lead with an
 * email or LinkedIn thread has a sequence that owns their follow-up date.
 *
 * The date comes from WhatsApp Calling (call_campaign_contacts.follow_up_at:
 * the retry schedule, the transcript's suggestion, or the rep), the earliest
 * across the lead's open campaign entries. Calling owns it: a new call or a
 * rep's edit re-syncs; nothing here writes back.
 */

export type FollowUpRecordState = {
  workflowState: CrmWorkflowState;
  nextActionAt: Date | null;
  activeChannel: CrmRecordChannel | null;
  latestInboundMessageId: string | null;
};

export type FollowUpRecordUpdate = {
  workflowState: "waiting" | "idle";
  nextActionAt: Date | null;
  activeChannel: "whatsapp";
};

/**
 * What a record becomes for a follow-up due at `dueAt` (null: none), or null
 * to leave it alone. Pure, for the tests.
 *
 * "waiting" with a date is how the CRM already holds a scheduled follow-up;
 * Action required lists it once the date passes. Only idle or waiting
 * records move: one that needs a person for another reason (a review, an
 * error), or is paused or closed, keeps its state.
 */
export function callFollowUpUpdate(record: FollowUpRecordState, dueAt: Date | null): FollowUpRecordUpdate | null {
  if (record.latestInboundMessageId) return null;
  if (record.activeChannel && record.activeChannel !== "whatsapp") return null;
  if (dueAt) {
    if (record.workflowState !== "idle" && record.workflowState !== "waiting") return null;
    const unchanged =
      record.workflowState === "waiting" &&
      record.activeChannel === "whatsapp" &&
      record.nextActionAt?.getTime() === dueAt.getTime();
    return unchanged ? null : { workflowState: "waiting", nextActionAt: dueAt, activeChannel: "whatsapp" };
  }
  // No follow-up any more: a record waiting on one goes back to idle.
  if (record.workflowState === "waiting") return { workflowState: "idle", nextActionAt: null, activeChannel: "whatsapp" };
  return null;
}

export async function syncCallFollowUp(personId: string): Promise<void> {
  const [[due], [spoken]] = await Promise.all([
    db
      .select({ followUpAt: min(callCampaignContacts.followUpAt) })
      .from(callCampaignContacts)
      .innerJoin(callCampaigns, eq(callCampaigns.id, callCampaignContacts.campaignId))
      .where(
        and(
          inOrg(callCampaigns),
          eq(callCampaignContacts.personId, personId),
          ne(callCampaignContacts.stage, "done"),
          isNotNull(callCampaignContacts.followUpAt),
          isNull(callCampaigns.archivedAt),
        ),
      ),
    db
      .select({ id: callSessions.id })
      .from(callSessions)
      .where(and(inOrg(callSessions), eq(callSessions.personId, personId), eq(callSessions.status, "recorded")))
      .limit(1),
  ]);
  const dueAt = due?.followUpAt ?? null;

  await withCrmTransaction(async (tx) => {
    const actor = { actorType: "integration" as const, actorRef: "whatsapp-calling" };
    let record = await lockRepresentativeRecord(tx, personId);
    if (!record) {
      if (!spoken || !dueAt) return;
      record = await lockOrCreateRecord(tx, personId, actor);
    }
    const update = callFollowUpUpdate(record, dueAt);
    if (!update) return;

    // A direct write rather than transitionWorkflow: that returns early when
    // the state is unchanged (a new date on a waiting record), and it does
    // not allow idle → waiting, which only sequences produced until now.
    const contextVersion = record.contextVersion + 1;
    await tx
      .update(crmRecords)
      .set({ ...update, contextVersion, updatedAt: new Date() })
      .where(and(inOrg(crmRecords), eq(crmRecords.id, record.id)));
    await appendCrmEvent(tx, {
      personId: record.personId,
      crmRecordId: record.id,
      pipelineId: record.pipelineId,
      eventType: "workflow.state_changed",
      ...actor,
      fromData: { workflowState: record.workflowState, nextActionAt: record.nextActionAt },
      toData: { workflowState: update.workflowState, nextActionAt: update.nextActionAt },
      meta: { reason: update.nextActionAt ? "Call follow-up scheduled" : "No call follow-up due" },
      contextVersion,
    });
  });
}

/** syncCallFollowUp that logs rather than throws: the calling change it follows has already been saved. */
export function syncCallFollowUpSafely(personId: string): Promise<void> {
  return syncCallFollowUp(personId).catch((error) => {
    console.error("Syncing the call follow-up to the CRM failed", personId, error);
  });
}
