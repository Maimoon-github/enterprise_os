import { and, desc, eq } from "drizzle-orm";
import type { CallTranscript } from "@/lib/calls/contract";
import { callSessions } from "@/lib/calls/schema";
import type { ClassificationMessage } from "./ai/types";
import type { CrmExecutor } from "./repository";
import { inOrg } from "@/lib/tenancy/scope";

/**
 * The lead's recent WhatsApp calls, as prompt context for a WhatsApp
 * conversation: a reply in the chat often follows a call ("as discussed…"),
 * and neither the classifier nor the drafter would otherwise know the call
 * happened.
 *
 * Deliberately not stored as crm_conversation_messages: a call is not a
 * message either side sent, and the thread would show its summary as one.
 * It is added to recentConversation when a prompt is built, with the
 * "whatsapp_call" channel the call classifier already uses
 * (calls/leadStageRules.ts); both prompts explain that channel.
 */

/** How many of the latest transcribed calls a prompt gets. */
export const CALL_CONTEXT_LIMIT = 3;

export type CallContextRow = {
  id: string;
  startedAt: Date | null;
  endedAt: Date | null;
  createdAt: Date;
  disposition: string | null;
  transcript: Pick<CallTranscript, "summary"> | null;
};

/** One call as a context message, or null when it has no summary. Pure. */
export function callContextMessage(row: CallContextRow): ClassificationMessage | null {
  const summary = row.transcript?.summary?.trim();
  if (!summary) return null;
  const outcome = row.disposition ? ` (the rep marked the outcome "${row.disposition}")` : "";
  return {
    id: `call:${row.id}`,
    channel: "whatsapp_call",
    // The rep placed it; the summary covers both sides.
    direction: "outbound",
    sentAt: row.endedAt ?? row.startedAt ?? row.createdAt,
    subject: "WhatsApp call summary",
    bodyText: `Summary of a WhatsApp voice call between the rep and this person${outcome}: ${summary}`,
  };
}

export async function loadCallContextMessages(
  executor: CrmExecutor,
  personId: string,
): Promise<ClassificationMessage[]> {
  const rows = await executor
    .select({
      id: callSessions.id,
      startedAt: callSessions.startedAt,
      endedAt: callSessions.endedAt,
      createdAt: callSessions.createdAt,
      disposition: callSessions.disposition,
      transcript: callSessions.transcript,
    })
    .from(callSessions)
    .where(and(inOrg(callSessions), eq(callSessions.personId, personId), eq(callSessions.transcriptStatus, "done")))
    .orderBy(desc(callSessions.createdAt))
    .limit(CALL_CONTEXT_LIMIT);
  return rows.flatMap((row) => {
    const message = callContextMessage(row);
    return message ? [message] : [];
  });
}
