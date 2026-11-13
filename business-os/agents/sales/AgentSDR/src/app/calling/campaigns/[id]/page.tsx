import { and, eq } from "drizzle-orm";
import { redirect } from "next/navigation";
import CampaignClient from "@/components/calling/CampaignClient";
import { isContactTab } from "@/components/calling/contactTabs";
import { requirePageOrgContext } from "@/lib/auth/context";
import { callCampaigns } from "@/lib/calls/schema";
import { db } from "@/lib/db";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";

export default async function CallCampaignPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string | string[] }>;
}) {
  const [{ id }, { tab }, ctx] = await Promise.all([params, searchParams, requirePageOrgContext()]);
  // An AI campaign has its own pages; this one is a rep's call list.
  const [campaign] = /^[0-9a-f-]{36}$/i.test(id)
    ? await runInOrganization(ctx.organizationId, () =>
        db.select({ runBy: callCampaigns.runBy }).from(callCampaigns).where(and(inOrg(callCampaigns), eq(callCampaigns.id, id))).limit(1),
      )
    : [];
  if (campaign?.runBy === "ai") redirect(`/calling/campaigns/ai/${id}`);
  return <CampaignClient campaignId={id} initialTab={isContactTab(tab) ? tab : "all"} />;
}
