/**
 * Hands a genuine inbound LinkedIn reply to the CRM, so email and LinkedIn
 * replies land in one shared triage inbox.
 *
 * The LinkedIn side has already done the hard work of resolving who the real
 * counterparty is (is_sender/attendees[] echo-filtering in the
 * message-received webhook) — the CRM only needs the resolved fields.
 *
 * The integration calls ingest directly, with duplicate suppression and a
 * durable inbound-event audit row before processing.
 *
 * Best-effort: any failure here is logged and swallowed. Forwarding must
 * never affect the LinkedIn side's own local save or its response to Unipile.
 */

import { db } from "@/lib/db";
import { inboundEvents } from "@/lib/inbox/schema";
import {
  processLinkedinInboundEvent,
  mapLinkedinPayload,
  isDuplicateLinkedinMessage,
} from "./ingestCrmReply";
import { currentOrganizationId } from "@/lib/tenancy/scope";

type ForwardPayload = {
  /** CRM forwarding is reserved for a canonical campaign Person. */
  personId: string;
  providerId: string;
  name: string | null;
  headline: string | null;
  linkedinUrl: string | null;
  chatId: string | null;
  accountId: string | null;
  accountUsername: string | null;
  messageText: string;
  linkedinMessageId: string | null;
  sentAt: Date | null;
};

export async function forwardReplyToAgentSdr(
  payload: ForwardPayload,
  options: { throwOnError?: boolean } = {},
): Promise<void> {
  try {
    // Keep the stored payload stable so failed deliveries remain replayable.
    const body = {
      personId: payload.personId,
      providerId: payload.providerId,
      name: payload.name,
      headline: payload.headline,
      linkedinUrl: payload.linkedinUrl,
      chatId: payload.chatId,
      accountId: payload.accountId,
      accountUsername: payload.accountUsername,
      messageText: payload.messageText,
      linkedinMessageId: payload.linkedinMessageId,
      sentAt: payload.sentAt ? payload.sentAt.toISOString() : null,
    };

    const mapped = mapLinkedinPayload(body);
    const title = mapped?.name || mapped?.providerId || null;

    if (mapped?.linkedinMessageId && (await isDuplicateLinkedinMessage(mapped.linkedinMessageId))) {
      await db.insert(inboundEvents).values({
        organizationId: currentOrganizationId(),
        source: "linkedin",
        eventType: "message_received",
        title,
        status: "skipped",
        steps: [
          {
            ts: new Date().toISOString(),
            level: "info",
            message: `Duplicate delivery — message ${mapped.linkedinMessageId} already stored`,
          },
        ],
        payload: body as object,
        processed: true,
      });
      return;
    }

    const [row] = await db
      .insert(inboundEvents)
      .values({
        organizationId: currentOrganizationId(),
        source: "linkedin",
        eventType: "message_received",
        title,
        payload: body as object,
        processed: false,
      })
      .returning({ id: inboundEvents.id });

    await processLinkedinInboundEvent(row.id);
  } catch (err) {
    console.error(
      "[forwardToAgentSdr] CRM forwarding failed:",
      err instanceof Error ? err.message : err
    );
    if (options.throwOnError) throw err;
  }
}
