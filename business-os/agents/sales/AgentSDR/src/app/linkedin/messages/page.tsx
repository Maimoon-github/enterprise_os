import { and, asc, eq, ne } from "drizzle-orm";
import { requirePageOrgContext } from "@/lib/auth/context";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { campaigns as campaignsTable, linkedInAccounts } from "@/lib/linkedin/schema";
import { MessagesLayout } from "@/components/linkedin/MessagesLayout";
import { DEFAULT_MESSAGES_STATUS_FILTER } from "@/lib/linkedin/messages/connectionList";
import { listConnectionsPage } from "@/lib/linkedin/messages/connectionList.server";

export const dynamic = "force-dynamic";

export default async function MessagesPage() {
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, async () => {
    const [campaigns, accounts, initialList] = await Promise.all([
      db
        .select({ id: campaignsTable.id, name: campaignsTable.name })
        .from(campaignsTable)
        .where(and(inOrg(campaignsTable), ne(campaignsTable.type, "PERSONAL")))
        .orderBy(asc(campaignsTable.name)),
      db
        .select({
          id: linkedInAccounts.id,
          username: linkedInAccounts.username,
          name: linkedInAccounts.name,
          profilePictureUrl: linkedInAccounts.profilePictureUrl,
        })
        .from(linkedInAccounts)
        .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.status, "CONNECTED")))
        .orderBy(asc(linkedInAccounts.username)),
      listConnectionsPage(1, { status: DEFAULT_MESSAGES_STATUS_FILTER }),
    ]);

    return (
      <MessagesLayout campaigns={campaigns} accounts={accounts} initialList={initialList} />
    );
  });
}
