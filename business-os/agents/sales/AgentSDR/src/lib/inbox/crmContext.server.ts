/**
 * Master Inbox's half of the inbox CRM readers: mapping an inbox contact to
 * its CRM conversation. The record-level reads are shared with the LinkedIn
 * inbox in @/lib/crm/inboxContext.server.
 *
 * An inbox contact (crm_leads, a legacy name) reaches the CRM through its
 * email: crm_leads.email ↔ people.email, case-insensitively, then the
 * Person's record on the default pipeline — the same join the list query
 * uses. Every active email conversation on that record is with this Person,
 * so the only question is which thread: prefer the conversation whose Gmail
 * thread id appears on one of the contact's stored messages, then the one
 * keyed by the contact's email, then the one on the contact's mailbox. Read
 * src/lib/crm/conversations.ts for why a conversation can carry a thread id,
 * a contact id, or both.
 */
import { and, desc, eq, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  type InboxCrmConversationScope,
  loadInboxCrmContextForConversation,
} from "@/lib/crm/inboxContext.server";
import { crmConversations, crmPipelines, crmRecords } from "@/lib/crm/schema";
import type { InboxCrmContext } from "@/lib/crm/inboxContext";
import { people } from "@/lib/leads/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { inboxContacts, inboxMessages } from "@/lib/inbox/schema";

export type { InboxCrmConversationScope };

/** The active CRM email conversation an inbox contact's thread belongs to, if any. */
export async function findCrmConversationForInboxContact(
  contactId: string,
): Promise<InboxCrmConversationScope | null> {
  const threadKnownToInbox = sql`EXISTS (
    SELECT 1 FROM ${inboxMessages} m
    WHERE m.lead_id = ${inboxContacts.id}
      AND m.raw->>'threadId' = ${crmConversations.providerThreadId}
  )`;
  const [scope] = await db
    .select({
      id: crmConversations.id,
      recordId: crmConversations.crmRecordId,
      personId: crmConversations.personId,
    })
    .from(inboxContacts)
    .innerJoin(people, and(inOrg(people), sql`lower(${people.email}) = lower(${inboxContacts.email})`))
    .innerJoin(crmPipelines, and(inOrg(crmPipelines), eq(crmPipelines.isDefault, true)))
    .innerJoin(crmRecords, and(eq(crmRecords.personId, people.id), eq(crmRecords.pipelineId, crmPipelines.id)))
    .innerJoin(
      crmConversations,
      and(
        eq(crmConversations.crmRecordId, crmRecords.id),
        eq(crmConversations.channel, "email"),
        eq(crmConversations.status, "active"),
      ),
    )
    .where(and(inOrg(inboxContacts), eq(inboxContacts.id, contactId)))
    .orderBy(
      sql`CASE
        WHEN ${crmConversations.providerThreadId} IS NOT NULL AND ${threadKnownToInbox} THEN 0
        WHEN lower(${crmConversations.providerContactId}) = lower(${inboxContacts.email}) THEN 1
        WHEN ${crmConversations.accountRef} = ${inboxContacts.mailbox} THEN 2
        ELSE 3
      END`,
      desc(crmConversations.updatedAt),
    )
    .limit(1);
  return scope ?? null;
}

/** Everything the open thread's CRM strip needs; null when the contact is not a CRM conversation. */
export async function loadInboxEmailCrmContext(contactId: string): Promise<InboxCrmContext | null> {
  const scope = await findCrmConversationForInboxContact(contactId);
  if (!scope) return null;
  return loadInboxCrmContextForConversation(scope);
}
