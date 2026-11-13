import "server-only";

import { and, eq, gt, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  RETRY_AFTER_DAYS,
  type CallStatus,
  type CampaignContactStage,
  type ContactCallStatus,
} from "./contract";
import { inOrg } from "@/lib/tenancy/scope";
import { callCampaignContacts, callCampaigns, callSessions, type CallDirection } from "./schema";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Statuses that count as an unanswered attempt on the retry schedule. */
const UNANSWERED: readonly ContactCallStatus[] = ["no_answer", "busy"];

/** call_campaign_contacts belongs to its campaign's organization (see campaigns.ts's contactInOrg). */
function contactInScope() {
  return inArray(callCampaignContacts.campaignId, db.select({ id: callCampaigns.id }).from(callCampaigns).where(inOrg(callCampaigns)));
}

export type ContactCallState = {
  callStatus: ContactCallStatus;
  stage: CampaignContactStage;
  unansweredAttempts: number;
  followUpAt: Date | null;
};

/**
 * What a lead's calling state becomes when a call (or the rep) sets a call
 * status. Pure, so the retry schedule is unit-testable:
 *
 *   calling           → only the status
 *   no_answer / busy  → one more unanswered attempt; due again in
 *                       RETRY_AFTER_DAYS[n-1] days, and done after the last
 *   connected         → attempts reset; into Follow-up, no date yet (the
 *                       transcript's analysis or the rep sets one)
 *   not on WhatsApp / wrong number → done
 *   failed            → only the status: nothing was learned about the lead
 *
 * `manual` is a rep correcting the last call's status. Swapping one
 * unanswered status for the other (no answer ↔ busy) relabels it without
 * counting a second attempt for the same call.
 */
export function nextContactCallState(
  current: ContactCallState,
  next: ContactCallStatus,
  now: Date,
  options: { manual?: boolean } = {},
): ContactCallState {
  switch (next) {
    case "new":
    case "calling":
    case "failed":
      return { ...current, callStatus: next };
    case "no_answer":
    case "busy": {
      if (options.manual && UNANSWERED.includes(current.callStatus)) return { ...current, callStatus: next };
      const attempts = current.unansweredAttempts + 1;
      const days = RETRY_AFTER_DAYS[attempts - 1];
      if (days === undefined) return { callStatus: next, stage: "done", unansweredAttempts: attempts, followUpAt: null };
      return {
        callStatus: next,
        // A lead already in Follow-up stays there while it is retried.
        stage: current.stage === "follow_up" ? "follow_up" : "to_call",
        unansweredAttempts: attempts,
        followUpAt: new Date(now.getTime() + days * DAY_MS),
      };
    }
    case "connected":
      return { callStatus: next, stage: "follow_up", unansweredAttempts: 0, followUpAt: null };
    case "not_on_whatsapp":
    case "wrong_number":
      return { ...current, callStatus: next, stage: "done", followUpAt: null };
  }
}

/** The calling state alone, out of a full row — what is safe to spread into an update. */
export function stateOf(row: ContactCallState): ContactCallState {
  return {
    callStatus: row.callStatus,
    stage: row.stage,
    unansweredAttempts: row.unansweredAttempts,
    followUpAt: row.followUpAt,
  };
}

/**
 * The call status a finished call leaves its lead in. The extension reports
 * "isn't on WhatsApp" as a failed call; an upload that failed after the lead
 * picked up still means they spoke.
 */
export function contactCallStatusForCall(call: { status: CallStatus; error: string | null }): ContactCallStatus {
  switch (call.status) {
    case "pending":
    case "in_progress":
      return "calling";
    case "recorded":
      return "connected";
    case "no_recording":
      return "no_answer";
    case "failed":
      if (call.error && /isn't on WhatsApp/i.test(call.error)) return "not_on_whatsapp";
      if (call.error && /^Upload failed/i.test(call.error)) return "connected";
      return "failed";
  }
}

/**
 * Applies a finished call's result to its campaign lead. Only the lead's
 * latest call may: a late report from an older call must not overwrite what
 * a newer one set. Locks the lead's row so two reports cannot both count an
 * attempt from the same starting point.
 */
export async function applyCallResultToContact(call: {
  id: string;
  campaignContactId: string | null;
  createdAt: Date;
  status: CallStatus;
  error: string | null;
  direction?: CallDirection;
}): Promise<void> {
  if (!call.campaignContactId) return;
  // A call they made to us that never connected is not an unanswered attempt of ours.
  if (call.direction === "inbound" && call.status !== "recorded") return;
  const contactId = call.campaignContactId;
  const next = contactCallStatusForCall(call);
  const personId = await db.transaction(async (tx) => {
    const [contact] = await tx
      .select()
      .from(callCampaignContacts)
      .where(and(contactInScope(), eq(callCampaignContacts.id, contactId)))
      .for("update")
      .limit(1);
    if (!contact) return null;
    const [newer] = await tx
      .select({ id: callSessions.id })
      .from(callSessions)
      .where(and(inOrg(callSessions), eq(callSessions.campaignContactId, contactId), gt(callSessions.createdAt, call.createdAt)))
      .limit(1);
    if (newer) return null;
    const now = new Date();
    // An AI campaign's lead: its engine owns the stage, retries and follow-up
    // date (aiCampaigns/engine.ts); only the call status shown is updated.
    if (contact.aiStatus !== null) {
      await tx
        .update(callCampaignContacts)
        .set({ callStatus: next, statusUpdatedAt: now, updatedAt: now })
        .where(and(contactInScope(), eq(callCampaignContacts.id, contactId)));
      return null;
    }
    const state = nextContactCallState(stateOf(contact), next, now);
    await tx
      .update(callCampaignContacts)
      .set({ ...state, statusUpdatedAt: now, updatedAt: now })
      .where(and(contactInScope(), eq(callCampaignContacts.id, contactId)));
    return contact.personId;
  });
  if (!personId) return;
  // Imported lazily: crmFollowUp reaches sessions.ts, which imports this module.
  const { syncCallFollowUpSafely } = await import("./crmFollowUp");
  await syncCallFollowUpSafely(personId);
}

/** applyCallResultToContact that logs rather than throws — the call's own report must not fail over it. */
export function applyCallResultToContactSafely(call: Parameters<typeof applyCallResultToContact>[0]): Promise<void> {
  return applyCallResultToContact(call).catch((error) => {
    console.error("Updating the campaign lead's call status failed", call.id, error);
  });
}

