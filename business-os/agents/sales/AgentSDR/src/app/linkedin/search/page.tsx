import { and, asc, eq } from "drizzle-orm";
import { channelRules } from "@/lib/channels/rules.server";
import { requirePageOrgContext } from "@/lib/auth/context";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { linkedInAccounts } from "@/lib/linkedin/schema";
import { listSearchBatches } from "@/lib/linkedin/searchBatches";
import { SearchBatchesClient } from "@/components/linkedin/SearchBatchesClient";

export const dynamic = "force-dynamic";

export default async function SearchPage() {
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, async () => {
    const [batches, accounts] = await Promise.all([
      listSearchBatches(),
      db
        .select({
          id: linkedInAccounts.id,
          username: linkedInAccounts.username,
          name: linkedInAccounts.name,
          profilePictureUrl: linkedInAccounts.profilePictureUrl,
          searchLeadsToday: linkedInAccounts.searchLeadsToday,
        })
        .from(linkedInAccounts)
        .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.status, "CONNECTED")))
        .orderBy(asc(linkedInAccounts.username))
        .then(async (rows) => {
          const { searchLeadsPerDay } = await channelRules("linkedin");
          return rows.map((row) => ({ ...row, searchLimit: searchLeadsPerDay }));
        }),
    ]);

    return <SearchBatchesClient initialBatches={batches} accounts={accounts} />;
  });
}
