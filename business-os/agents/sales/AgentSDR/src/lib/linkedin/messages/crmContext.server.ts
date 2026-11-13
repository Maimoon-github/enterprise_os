/**
 * LinkedIn's half of the inbox CRM readers: mapping a connection to its CRM
 * conversation. The record-level reads (summary, strip context) are shared
 * with the email Master Inbox in @/lib/crm/inboxContext.server.
 *
 * A LinkedIn connection is a CRM conversation when crm_conversations has a
 * live linkedin row for the connection's Unipile chat id, scoped to the
 * account that owns the connection. Note that `account_ref` is the Unipile
 * account id (LinkedInAccount.linkedinId), not LinkedInAccount.id — the two
 * are joined through the account row.
 */
import { and, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { crmConversations } from "@/lib/crm/schema";
import {
  type InboxCrmConversationScope,
  loadInboxCrmContextForConversation,
  loadInboxCrmSummariesForRecords,
} from "@/lib/crm/inboxContext.server";
import { connections, linkedInAccounts } from "@/lib/linkedin/schema";
import { inOrg } from "@/lib/tenancy/scope";
import type { InboxCrmContext, InboxCrmSummary } from "./crmContext";

export type { InboxCrmConversationScope };

/** The active CRM conversation a LinkedIn thread belongs to, if any. */
export async function findCrmConversationForConnection(connection: {
  chatId: string | null;
  linkedinAccountId: string | null;
}): Promise<InboxCrmConversationScope | null> {
  if (!connection.chatId || !connection.linkedinAccountId) return null;
  const [scope] = await db
    .select({
      id: crmConversations.id,
      recordId: crmConversations.crmRecordId,
      personId: crmConversations.personId,
    })
    .from(crmConversations)
    .innerJoin(
      linkedInAccounts,
      and(
        inOrg(linkedInAccounts),
        eq(linkedInAccounts.id, connection.linkedinAccountId),
        eq(linkedInAccounts.linkedinId, crmConversations.accountRef),
      ),
    )
    .where(
      and(
        inOrg(crmConversations),
        eq(crmConversations.channel, "linkedin"),
        eq(crmConversations.providerThreadId, connection.chatId),
        eq(crmConversations.status, "active"),
      ),
    )
    .limit(1);
  return scope ?? null;
}

/**
 * List-row summaries for a page of connections, keyed by connection id.
 * Batched: one account lookup, one conversation match, then the record-level
 * reads — never a query per row.
 */
export async function loadInboxCrmSummaries(
  connections: { id: string; chatId: string | null; linkedInAccountId: string | null }[],
): Promise<Map<string, InboxCrmSummary>> {
  const summaries = new Map<string, InboxCrmSummary>();
  const candidates = connections.filter(
    (c): c is { id: string; chatId: string; linkedInAccountId: string } =>
      Boolean(c.chatId && c.linkedInAccountId),
  );
  if (candidates.length === 0) return summaries;

  const accountIds = [...new Set(candidates.map((c) => c.linkedInAccountId))];
  const accounts = await db
    .select({ id: linkedInAccounts.id, linkedinId: linkedInAccounts.linkedinId })
    .from(linkedInAccounts)
    .where(and(inOrg(linkedInAccounts), inArray(linkedInAccounts.id, accountIds)));
  const unipileIdByAccount = new Map(accounts.map((a) => [a.id, a.linkedinId]));

  // A thread is identified by (account_ref, provider_thread_id); the unique
  // index on crm_conversations guarantees at most one active row per pair.
  const connectionByThread = new Map<string, string>();
  for (const c of candidates) {
    const unipileId = unipileIdByAccount.get(c.linkedInAccountId);
    if (unipileId) connectionByThread.set(`${unipileId} ${c.chatId}`, c.id);
  }
  if (connectionByThread.size === 0) return summaries;

  const matches = await db
    .select({
      accountRef: crmConversations.accountRef,
      providerThreadId: crmConversations.providerThreadId,
      recordId: crmConversations.crmRecordId,
    })
    .from(crmConversations)
    .where(
      and(
        inOrg(crmConversations),
        eq(crmConversations.channel, "linkedin"),
        eq(crmConversations.status, "active"),
        inArray(crmConversations.accountRef, [...new Set(accounts.map((a) => a.linkedinId))]),
        inArray(crmConversations.providerThreadId, [...new Set(candidates.map((c) => c.chatId))]),
      ),
    );

  const recordByConnection = new Map<string, string>();
  for (const row of matches) {
    const connectionId = connectionByThread.get(`${row.accountRef} ${row.providerThreadId}`);
    if (connectionId) recordByConnection.set(connectionId, row.recordId);
  }
  const byRecord = await loadInboxCrmSummariesForRecords([...recordByConnection.values()]);
  for (const [connectionId, recordId] of recordByConnection) {
    const summary = byRecord.get(recordId);
    if (summary) summaries.set(connectionId, summary);
  }
  return summaries;
}

/** Everything the open thread's CRM strip needs; null when the thread is not a CRM conversation. */
export async function loadInboxCrmContext(connectionId: string): Promise<InboxCrmContext | null> {
  const [connection] = await db
    .select({ chatId: connections.chatId, linkedinAccountId: connections.linkedinAccountId })
    .from(connections)
    .where(and(inOrg(connections), eq(connections.id, connectionId)))
    .limit(1);
  if (!connection) return null;
  const scope = await findCrmConversationForConnection(connection);
  if (!scope) return null;
  return loadInboxCrmContextForConversation(scope);
}
