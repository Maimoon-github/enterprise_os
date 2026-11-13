import { and, eq, isNotNull, isNull, lt, lte, or, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { leads } from "./schema";
import { inOrg } from "@/lib/tenancy/scope";
import { MAX_LEAD_RETRIES, type LeadRetryContext } from "./inviteRetry";

export const PROFILE_RESOLUTION_LEASE_MS = 5 * 60 * 1000;

/** Atomically lease an unresolved Lead before making a provider lookup. */
export const claimLeadForResolution = async (leadId: string, now = new Date()): Promise<boolean> => {
  const [claimed] = await db
    .update(leads)
    .set({ resolveNextAttemptAt: new Date(now.getTime() + PROFILE_RESOLUTION_LEASE_MS) })
    .where(and(
      inOrg(leads),
      eq(leads.id, leadId),
      eq(leads.status, "PENDING"),
      isNotNull(leads.sourceLinkedinIdentifier),
      lt(leads.resolveRetryCount, MAX_LEAD_RETRIES),
      or(isNull(leads.resolveNextAttemptAt), lte(leads.resolveNextAttemptAt, now)),
    ))
    .returning({ id: leads.id });
  return Boolean(claimed);
};

/**
 * Server-only retry bookkeeping. Split from ./inviteRetry so client components
 * can import MAX_LEAD_RETRIES (LeadDetailPanel renders "Retries: n/max")
 * without pulling the postgres driver into the browser bundle.
 */

export const resetLeadRetryCount = async (leadId: string): Promise<void> => {
  await db.update(leads).set({ inviteRetryCount: 0 }).where(and(inOrg(leads), eq(leads.id, leadId)));
};

/** Bump retry count on failure; mark FAILED after max retries. */
export const recordLeadRetryFailure = async (
  leadId: string,
  context: LeadRetryContext
): Promise<void> => {
  const [lead] = await db
    .update(leads)
    .set({
      inviteRetryCount: sql`${leads.inviteRetryCount} + 1`,
      ...(context === "sendInvitations"
        ? {
            status: "PENDING" as const,
            linkedinAccountId: null,
            requestSentAt: null,
          }
        : {}),
    })
    .where(and(inOrg(leads), eq(leads.id, leadId)))
    .returning({ id: leads.id, inviteRetryCount: leads.inviteRetryCount });

  if (lead.inviteRetryCount >= MAX_LEAD_RETRIES) {
    await db.update(leads).set({ status: "FAILED" }).where(and(inOrg(leads), eq(leads.id, leadId)));
    console.warn(
      `[${context}] Lead ${lead.id} marked FAILED after ${lead.inviteRetryCount} failed attempt(s)`
    );
    return;
  }

  console.warn(
    `[${context}] Lead ${lead.id} failed — retry ${lead.inviteRetryCount}/${MAX_LEAD_RETRIES}`
  );
};

/**
 * Bump the resolve retry count, then either schedule a backoff or give up.
 * A locked, deleted or renamed profile fails permanently, so the budget is the
 * same MAX_LEAD_RETRIES the invite and follow-up senders use — past it the lead
 * becomes FAILED rather than sitting at PENDING where nothing will claim it.
 */
export const recordResolveFailure = async (leadId: string, error: string): Promise<void> => {
  const [lead] = await db.select({ retryCount: leads.resolveRetryCount }).from(leads).where(and(inOrg(leads), eq(leads.id, leadId))).limit(1);
  if (!lead) return;
  const retryCount = lead.retryCount + 1;
  const lastError = error.slice(0, 2000);

  if (retryCount >= MAX_LEAD_RETRIES) {
    await db.update(leads).set({
      resolveRetryCount: retryCount,
      resolveNextAttemptAt: null,
      resolveLastError: lastError,
      status: "FAILED",
    }).where(and(inOrg(leads), eq(leads.id, leadId)));
    console.warn(
      `[resolveProfiles] Lead ${leadId} marked FAILED after ${retryCount} resolution attempt(s): ${lastError}`
    );
    return;
  }

  const delayMinutes = Math.min(60 * 2 ** Math.max(retryCount - 1, 0), 24 * 60);
  await db.update(leads).set({
    resolveRetryCount: retryCount,
    resolveNextAttemptAt: new Date(Date.now() + delayMinutes * 60_000),
    resolveLastError: lastError,
  }).where(and(inOrg(leads), eq(leads.id, leadId)));
  console.warn(
    `[resolveProfiles] Lead ${leadId} resolution failed — retry ${retryCount}/${MAX_LEAD_RETRIES} after ${delayMinutes} minute(s)`
  );
};

export const recordInviteSendFailure = (leadId: string) =>
  recordLeadRetryFailure(leadId, "sendInvitations");

/**
 * A follow-up failed to send (blocked chat, revoked account, Unipile error).
 * Keeps failure bookkeeping on the current follow-up status. A failure before
 * a delivery claim can retry; an uncertain provider outcome retains its
 * Message claim and the sender stops it for reconciliation.
 */
export const recordFollowUpSendFailure = (leadId: string) =>
  recordLeadRetryFailure(leadId, "sendFollowUps");
