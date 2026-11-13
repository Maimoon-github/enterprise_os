import { notFound } from "next/navigation";
import { channelRules } from "@/lib/channels/rules.server";
import { requirePageOrgContext } from "@/lib/auth/context";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { linkedInAccounts } from "@/lib/linkedin/schema";
import { getSearchBatchDetail, isSearchJobRunning } from "@/lib/linkedin/searchBatches";
import { SearchBatchDetailClient } from "@/components/linkedin/SearchBatchDetailClient";

export const dynamic = "force-dynamic";

export default async function SearchBatchPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, async () => {
    const { id } = await params;

    const [detail, jobRunning, accounts] = await Promise.all([
      getSearchBatchDetail(id),
      isSearchJobRunning(),
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

    if (!detail) notFound();

    return <SearchBatchDetailClient initialDetail={detail} initialJobRunning={jobRunning} accounts={accounts} />;
  });
}
