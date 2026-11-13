import { notFound } from "next/navigation";
import CampaignDetailClient from "@/components/outreach/CampaignDetailClient";
import {
  getCampaign,
  getCampaignStats,
  getCampaignLeadsPage,
  getCampaignStepBreakdown,
  getCampaignDailySends,
  getCampaignPulse,
} from "@/lib/outreach/campaigns";
import { listMailboxes } from "@/lib/outreach/mailboxes";
import { requirePageOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

export const dynamic = "force-dynamic";

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, () => renderCampaign(id));
}

async function renderCampaign(id: string) {
  const campaign = await getCampaign(id);
  if (!campaign) notFound();

  // Only the first page of leads is serialized into the document — a campaign
  // with thousands of leads would otherwise ship ~0.9MB of JSON per page load.
  const [stats, mailboxes, leadPage, stepBreakdown, dailySends, pulse] = await Promise.all([
    getCampaignStats(id),
    listMailboxes(),
    getCampaignLeadsPage(id, { page: 1 }),
    getCampaignStepBreakdown(id),
    getCampaignDailySends(id, { days: 30, timeZone: "Asia/Kolkata" }),
    getCampaignPulse(id),
  ]);

  return (
    <div className="flex h-full overflow-hidden bg-bg-white-0">
      <div className="min-w-0 flex-1 overflow-y-auto">
        <CampaignDetailClient
          campaign={campaign}
          stats={stats}
          mailboxes={mailboxes}
          leadPage={leadPage}
          stepBreakdown={stepBreakdown}
          dailySends={dailySends}
          pulse={pulse}
        />
      </div>
    </div>
  );
}
