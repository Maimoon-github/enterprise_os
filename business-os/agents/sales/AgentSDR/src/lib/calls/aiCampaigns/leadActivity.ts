import "server-only";

import { and, desc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { whatsappAccounts, whatsappChats, whatsappMessages } from "@/lib/whatsapp/schema";
import { crmStageForPeople } from "../leadStage";
import { callCampaignContacts, callCampaignStepRuns, callCampaigns, callSessions, callingStations, stationMessageJobs } from "../schema";
import { toCallSummary } from "../sessions";
import { aiStepLabel, describeStepKey, type AiActivityCallResult, type AiLeadActivity, type AiLeadActivitySummary } from "./api";

type CampaignRow = typeof callCampaigns.$inferSelect;
type SessionRow = typeof callSessions.$inferSelect;

const MAX_CALLS = 60;
const MAX_MESSAGES = 120;

/**
 * Everything that happened with a lead's person, newest first: every call
 * (this campaign's steps, a rep's own calls, other campaigns) and every
 * WhatsApp message either way, plus this campaign's steps that failed before
 * a call or message existed. Runs in the organization's scope.
 */
export async function loadLeadActivity(
  campaign: CampaignRow,
  contact: { id: string; personId: string },
): Promise<{ activity: AiLeadActivity[]; summary: AiLeadActivitySummary }> {
  const [runs, calls, messages, stages] = await Promise.all([
    db.select().from(callCampaignStepRuns).where(eq(callCampaignStepRuns.contactId, contact.id)),
    db
      .select({ session: callSessions, campaignId: callCampaignContacts.campaignId, campaignName: callCampaigns.name, numberName: callingStations.name })
      .from(callSessions)
      .leftJoin(callCampaignContacts, eq(callCampaignContacts.id, callSessions.campaignContactId))
      .leftJoin(callCampaigns, and(eq(callCampaigns.id, callCampaignContacts.campaignId), inOrg(callCampaigns)))
      .leftJoin(callingStations, and(eq(callingStations.id, callSessions.stationId), inOrg(callingStations)))
      .where(and(inOrg(callSessions), eq(callSessions.personId, contact.personId)))
      .orderBy(desc(callSessions.createdAt))
      .limit(MAX_CALLS),
    db
      .select({
        message: whatsappMessages,
        numberName: whatsappAccounts.name,
        numberPhone: whatsappAccounts.phone,
        jobStatus: stationMessageJobs.status,
        jobError: stationMessageJobs.error,
      })
      .from(whatsappMessages)
      .innerJoin(whatsappChats, eq(whatsappChats.id, whatsappMessages.chatId))
      .innerJoin(whatsappAccounts, eq(whatsappAccounts.id, whatsappChats.accountId))
      .leftJoin(stationMessageJobs, eq(stationMessageJobs.whatsappMessageId, whatsappMessages.id))
      .where(and(inOrg(whatsappAccounts), eq(whatsappChats.personId, contact.personId)))
      .orderBy(desc(whatsappMessages.sentAt))
      .limit(MAX_MESSAGES),
    crmStageForPeople([contact.personId]).catch(() => new Map()),
  ]);

  const stepOf = (stepKey: string): string => {
    const described = describeStepKey(stepKey);
    const steps = described.phase === "chase" ? campaign.aiChaseSteps : campaign.aiSteps;
    const index = described.stepId ? steps.findIndex((step) => step.id === described.stepId) : -1;
    const position = index >= 0 ? aiStepLabel(steps, index, false) : null;
    return position ? `${described.label} · ${position}` : described.label;
  };
  const stepByCall = new Map(runs.flatMap((run) => (run.callSessionId ? [[run.callSessionId, stepOf(run.stepKey)] as const] : [])));
  const stepByMessage = new Map(runs.flatMap((run) => (run.whatsappMessageId ? [[run.whatsappMessageId, stepOf(run.stepKey)] as const] : [])));

  const activity: AiLeadActivity[] = [];
  for (const { session, campaignId, campaignName, numberName } of calls) {
    activity.push({
      id: session.id,
      at: (session.startedAt ?? session.createdAt).toISOString(),
      kind: "call",
      stepLabel: stepByCall.get(session.id) ?? null,
      campaignName: campaignId && campaignId !== campaign.id ? campaignName : null,
      call: {
        id: session.id,
        status: session.status,
        mode: session.mode,
        remoteRep: !!session.remoteRep,
        direction: session.direction,
        numberName: numberName ?? null,
        result: callResult(session),
        durationMs: session.durationMs,
        error: session.error,
        hasRecording: toCallSummary(session).hasRecording,
        recordingOffsetMs: session.recordingOffsetMs,
        transcriptStatus: session.transcriptStatus,
        outcome: session.agentOutcome
          ? { outcome: session.agentOutcome.outcome, summary: session.agentOutcome.summary, when: session.agentOutcome.when }
          : null,
      },
      message: null,
      error: null,
    });
  }
  for (const { message, numberName, numberPhone, jobStatus, jobError } of messages) {
    const uncertain = (message.raw as { status?: unknown } | null)?.status === "uncertain";
    activity.push({
      id: message.id,
      at: message.sentAt.toISOString(),
      kind: "message",
      stepLabel: stepByMessage.get(message.id) ?? null,
      campaignName: null,
      call: null,
      message: {
        direction: message.direction,
        origin: message.origin,
        body: message.body,
        numberName: numberName ?? numberPhone ?? null,
        delivery: uncertain ? "uncertain" : jobStatus === "queued" ? "queued" : jobStatus === "claimed" ? "sending" : jobStatus === "failed" ? "failed" : null,
        error: jobStatus === "failed" ? jobError : null,
      },
      error: null,
    });
  }
  // This campaign's steps that never got as far as a call or a message.
  const seenCalls = new Set(calls.map((row) => row.session.id));
  const seenMessages = new Set(messages.map((row) => row.message.id));
  for (const run of runs) {
    if (run.callSessionId && seenCalls.has(run.callSessionId)) continue;
    if (run.whatsappMessageId && seenMessages.has(run.whatsappMessageId)) continue;
    if (run.callSessionId || run.whatsappMessageId) continue; // Older than what is listed.
    activity.push({
      id: run.id,
      at: run.createdAt.toISOString(),
      kind: "step",
      stepLabel: stepOf(run.stepKey),
      campaignName: null,
      call: null,
      message: null,
      error: run.error ?? (run.status === "started" ? "Starting…" : "It did not start"),
    });
  }
  activity.sort((a, b) => b.at.localeCompare(a.at));

  const stage = stages.get(contact.personId);
  return {
    activity,
    summary: {
      calls: calls.length,
      connected: calls.filter((row) => row.session.status === "recorded").length,
      messagesSent: messages.filter((row) => row.message.direction === "outbound").length,
      messagesReceived: messages.filter((row) => row.message.direction === "inbound").length,
      lastActivityAt: activity[0]?.at ?? null,
      crmStage: stage?.subcategoryName ?? null,
    },
  };
}

function callResult(session: SessionRow): AiActivityCallResult {
  switch (session.status) {
    case "pending":
      return "queued";
    case "in_progress":
      return "in_progress";
    case "recorded":
      return "connected";
    case "no_recording":
      return "no_answer";
    default:
      return /isn.t on WhatsApp/i.test(session.error ?? "") ? "not_on_whatsapp" : "failed";
  }
}
