import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { createStepLogger, type StepLogger } from "@/lib/debugLog";
import { people } from "@/lib/leads/schema";
import { upsertPerson, withLeadTransaction } from "@/lib/leads/records";
import { ingestInboundReply } from "@/lib/crm/conversations";
import { quarantineCrmIdentity } from "@/lib/crm/identity";
import { crmConversationMessages, crmConversations } from "@/lib/crm/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { inboundEvents } from "@/lib/inbox/schema";

export type LinkedinReplyPayload = {
  personId: string | null;
  providerId: string;
  name: string | null;
  headline: string | null;
  linkedinUrl: string | null;
  chatId: string | null;
  accountId: string | null;
  accountUsername: string | null;
  messageText: string;
  linkedinMessageId: string | null;
  sentAt: string | null;
};

export function mapLinkedinPayload(payload: unknown): LinkedinReplyPayload | null {
  const candidate = payload as Partial<LinkedinReplyPayload> & Record<string, unknown>;
  const providerId = typeof candidate.providerId === "string" ? candidate.providerId.trim() : null;
  if (!providerId) return null;
  return {
    personId: typeof candidate.personId === "string" ? candidate.personId : null,
    providerId,
    name: typeof candidate.name === "string" ? candidate.name : null,
    headline: typeof candidate.headline === "string" ? candidate.headline : null,
    linkedinUrl: typeof candidate.linkedinUrl === "string" ? candidate.linkedinUrl : null,
    chatId: typeof candidate.chatId === "string" ? candidate.chatId : null,
    accountId: typeof candidate.accountId === "string" ? candidate.accountId : null,
    accountUsername: typeof candidate.accountUsername === "string" ? candidate.accountUsername : null,
    messageText: typeof candidate.messageText === "string" ? candidate.messageText : "",
    linkedinMessageId: typeof candidate.linkedinMessageId === "string" ? candidate.linkedinMessageId : null,
    sentAt: typeof candidate.sentAt === "string" ? candidate.sentAt : null,
  };
}

async function ingestMappedReply(mapped: LinkedinReplyPayload, log: StepLogger, eventId: string) {
  const sourceEventKey = mapped.linkedinMessageId ?? `linkedin:event:${eventId}`;
  if (!mapped.accountId) {
    await quarantineCrmIdentity({
      channel: "linkedin",
      accountRef: "unknown",
      sourceEventKey,
      identityValue: mapped.providerId,
      reason: "Inbound LinkedIn reply has no connected account ID",
      payload: mapped as unknown as Record<string, unknown>,
    });
    return { recordId: null, skipped: true as const };
  }
  if (!mapped.messageText.trim()) throw new Error("CRM cannot ingest an empty LinkedIn reply");

  let person;
  if (mapped.personId) {
    [person] = await db.select().from(people).where(and(inOrg(people), eq(people.id, mapped.personId))).limit(1);
    if (!person) {
      await quarantineCrmIdentity({
        channel: "linkedin",
        accountRef: mapped.accountId,
        sourceEventKey,
        identityValue: mapped.providerId,
        reason: `Referenced canonical Person ${mapped.personId} was not found`,
        payload: mapped as unknown as Record<string, unknown>,
      });
      return { recordId: null, skipped: true as const };
    }
  } else {
    if (!mapped.linkedinUrl) {
      await quarantineCrmIdentity({
        channel: "linkedin",
        accountRef: mapped.accountId,
        sourceEventKey,
        identityValue: mapped.providerId,
        reason: "LinkedIn reply has no canonical Person or public profile identity",
        payload: mapped as unknown as Record<string, unknown>,
      });
      return { recordId: null, skipped: true as const };
    }
    try {
      person = await withLeadTransaction((tx) => upsertPerson(tx, {
        linkedinUrl: mapped.linkedinUrl,
        fullName: mapped.name,
        title: mapped.headline,
        source: "crm:linkedin-inbound",
      }));
    } catch (error) {
      await quarantineCrmIdentity({
        channel: "linkedin",
        accountRef: mapped.accountId,
        sourceEventKey,
        identityValue: mapped.linkedinUrl,
        reason: `LinkedIn identity could not be resolved safely: ${error instanceof Error ? error.message : String(error)}`,
        payload: mapped as unknown as Record<string, unknown>,
      });
      return { recordId: null, skipped: true as const };
    }
  }

  const sentAt = mapped.sentAt ? new Date(mapped.sentAt) : new Date();
  const result = await ingestInboundReply({
    personId: person.id,
    channel: "linkedin",
    accountRef: mapped.accountId,
    providerThreadId: mapped.chatId,
    providerContactId: mapped.providerId,
    idempotencyKey: sourceEventKey,
    providerMessageId: mapped.linkedinMessageId,
    bodyText: mapped.messageText,
    raw: mapped as unknown as Record<string, unknown>,
    sentAt: Number.isNaN(sentAt.getTime()) ? new Date() : sentAt,
    actorRef: "unipile",
  });
  log.info(result.duplicate ? "CRM already stored this LinkedIn reply" : "LinkedIn reply routed to CRM");
  return { recordId: result.record.id, skipped: result.duplicate };
}

export async function processLinkedinInboundEvent(eventId: string) {
  const [row] = await db.select().from(inboundEvents).where(and(inOrg(inboundEvents), eq(inboundEvents.id, eventId))).limit(1);
  if (!row) throw new Error(`Inbound event not found: ${eventId}`);

  const log = createStepLogger();
  log.info(`${row.eventType ?? "unknown event"} — processing LinkedIn delivery`);
  try {
    const mapped = mapLinkedinPayload(row.payload);
    if (!mapped) {
      log.warn("Payload missing a resolvable providerId — skipping");
      log.finish("skipped");
      await db.update(inboundEvents).set({
        processed: true,
        error: "payload missing providerId; skipped",
        status: log.status,
        steps: log.steps,
      }).where(and(inOrg(inboundEvents), eq(inboundEvents.id, eventId)));
      return;
    }
    const result = await ingestMappedReply(mapped, log, eventId);
    log.finish(result.skipped ? "skipped" : "ok");
    await db.update(inboundEvents).set({
      processed: true,
      error: null,
      title: mapped.name || mapped.providerId,
      status: log.status,
      steps: log.steps,
    }).where(and(inOrg(inboundEvents), eq(inboundEvents.id, eventId)));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    log.error(message);
    log.finish("error");
    await db.update(inboundEvents).set({ error: message, status: log.status, steps: log.steps })
      .where(and(inOrg(inboundEvents), eq(inboundEvents.id, eventId)));
    throw error;
  }
}

export async function isDuplicateLinkedinMessage(providerMessageId: string | null): Promise<boolean> {
  if (!providerMessageId) return false;
  const [existing] = await db.select({ id: crmConversationMessages.id })
    .from(crmConversationMessages)
    .innerJoin(crmConversations, eq(crmConversations.id, crmConversationMessages.conversationId))
    .where(and(
      inOrg(crmConversations),
      eq(crmConversationMessages.channel, "linkedin"),
      eq(crmConversationMessages.providerMessageId, providerMessageId),
    ))
    .limit(1);
  return Boolean(existing);
}
