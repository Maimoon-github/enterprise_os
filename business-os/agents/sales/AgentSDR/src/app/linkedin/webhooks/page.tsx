import { and, count, desc, eq, inArray } from "drizzle-orm";
import { requirePageOrgContext } from "@/lib/auth/context";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { connections, linkedInAccounts, webhookEvents } from "@/lib/linkedin/schema";
import { PageHeader } from "@/components/page/PageHeader";
import { WebhooksClient, type WebhookEventRow } from "@/components/linkedin/WebhooksClient";
import { ListPagination } from "@/components/linkedin/ListPagination";
import { clampPage, pageSlice, parsePageParam } from "@/lib/linkedin/pagination";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<{ page?: string }>;
};

export default async function WebhooksPage({ searchParams }: Props) {
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, async () => {
    const { page: pageParam } = await searchParams;
    const [{ totalCount }] = await db.select({ totalCount: count() }).from(webhookEvents).where(inOrg(webhookEvents));
    const page = clampPage(parsePageParam(pageParam), totalCount);
    const { skip, take } = pageSlice(page);

    // `connection: { select: { name, profilePictureUrl } }` becomes a leftJoin
    // (connectionId is nullable) reshaped back into `connection`.
    const eventRows = await db
      .select({
        id: webhookEvents.id,
        event: webhookEvents.event,
        accountId: webhookEvents.accountId,
        senderId: webhookEvents.senderId,
        chatId: webhookEvents.chatId,
        messageText: webhookEvents.messageText,
        createdAt: webhookEvents.createdAt,
        processingStatus: webhookEvents.processingStatus,
        connectionId: connections.id,
        connectionName: connections.name,
        connectionProfilePictureUrl: connections.profilePictureUrl,
      })
      .from(webhookEvents)
      .leftJoin(connections, eq(webhookEvents.connectionId, connections.id))
      .where(inOrg(webhookEvents))
      .orderBy(desc(webhookEvents.createdAt))
      .limit(take)
      .offset(skip);

    const events = eventRows.map((r) => ({
      id: r.id,
      event: r.event,
      accountId: r.accountId,
      senderId: r.senderId,
      chatId: r.chatId,
      messageText: r.messageText,
      createdAt: r.createdAt,
      processingStatus: r.processingStatus,
      // `connectionId` distinguishes "no joined row" from "joined row whose
      // name/profilePictureUrl are both null" — the client tests `ev.connection`
      // for truthiness.
      connection: r.connectionId
        ? { name: r.connectionName, profilePictureUrl: r.connectionProfilePictureUrl }
        : null,
    }));

    const accountIds = [...new Set(events.map((e) => e.accountId).filter(Boolean))] as string[];
    const accounts = accountIds.length
      ? await db
          .select({
            linkedinId: linkedInAccounts.linkedinId,
            username: linkedInAccounts.username,
            name: linkedInAccounts.name,
            profilePictureUrl: linkedInAccounts.profilePictureUrl,
          })
          .from(linkedInAccounts)
          .where(and(inOrg(linkedInAccounts), inArray(linkedInAccounts.linkedinId, accountIds)))
      : [];

    const accountByLinkedinId = Object.fromEntries(accounts.map((a) => [a.linkedinId, a]));

    const rows: WebhookEventRow[] = events.map((ev) => ({
      id: ev.id,
      event: ev.event,
      accountId: ev.accountId,
      senderId: ev.senderId,
      chatId: ev.chatId,
      messageText: ev.messageText,
      createdAt: ev.createdAt.toISOString(),
      connection: ev.connection ?? null,
      account: ev.accountId ? (accountByLinkedinId[ev.accountId] ?? null) : null,
      processingStatus: ev.processingStatus ?? null,
    }));

    return (
      <div className="mx-auto w-full max-w-[1440px]">
        <PageHeader
          title="LinkedIn webhooks"
          description={
            totalCount === 0
              ? "Processing logs and raw payloads from Unipile"
              : `${totalCount.toLocaleString("en-US")} event${totalCount === 1 ? "" : "s"} received from Unipile, newest first`
          }
        />
        <WebhooksClient events={rows} footer={<ListPagination basePath="/linkedin/webhooks" page={page} totalCount={totalCount} />} />
      </div>
    );
  });
}
