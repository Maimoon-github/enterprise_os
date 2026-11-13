import { requirePageOrgContext } from "@/lib/auth/context";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { and, asc, eq } from "drizzle-orm";
import { LinkedInCampaignWizard } from "@/components/linkedin/LinkedInCampaignWizard";
import { db } from "@/lib/db";
import { linkedInAccounts } from "@/lib/linkedin/schema";

export const dynamic = "force-dynamic";

export default async function NewLinkedInCampaignPage() {
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, async () => {
    const accounts = await db
      .select({
        id: linkedInAccounts.id,
        username: linkedInAccounts.username,
        name: linkedInAccounts.name,
        profilePictureUrl: linkedInAccounts.profilePictureUrl,
      })
      .from(linkedInAccounts)
      .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.status, "CONNECTED")))
      .orderBy(asc(linkedInAccounts.username));

    return <LinkedInCampaignWizard accounts={accounts} />;
  });
}
