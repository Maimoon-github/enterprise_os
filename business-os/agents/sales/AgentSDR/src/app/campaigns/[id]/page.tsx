import Link from "next/link";
import { notFound } from "next/navigation";
import CampaignDetailClient from "@/components/campaigns/CampaignDetailClient";
import { requirePageOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { getCampaign, getCampaignDomains } from "@/lib/qualification";
import { getActiveCampaignJob } from "@/lib/qualification/jobRunner";

export const dynamic = "force-dynamic";

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const ctx = await requirePageOrgContext();
  const { campaign, domains, activeJob } = await runInOrganization(ctx.organizationId, async () => {
    const campaign = await getCampaign(id);
    if (!campaign) return { campaign: null, domains: [], activeJob: null };
    return { campaign, domains: await getCampaignDomains(id), activeJob: await getActiveCampaignJob(id) };
  });
  if (!campaign) notFound();

  return (
    <div className="h-full flex overflow-hidden bg-bg-weak-50">
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-stroke-soft-200 bg-bg-white-0 flex items-center gap-3">
          <Link href="/campaigns" className="text-text-strong-950/40 hover:text-text-strong-950 transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </Link>
          <div>
            <h1 className="text-base font-bold text-text-strong-950">{campaign.name}</h1>
            <p className="text-xs text-text-strong-950/50">
              {campaign.inputMode} campaign · {campaign.status}
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <CampaignDetailClient
            campaign={{
              id: campaign.id,
              name: campaign.name,
              status: campaign.status,
              targetMode: campaign.targetMode,
              targetLeadCount: campaign.targetLeadCount,
              targetDomainCount: campaign.targetDomainCount,
              accumulatedLeadCount: campaign.accumulatedLeadCount,
              apolloLink: campaign.apolloLink,
              inputMode: campaign.inputMode,
            }}
            activeJob={
              activeJob
                ? {
                    id: activeJob.id,
                    status: activeJob.status,
                    currentDomain: activeJob.currentDomain,
                  }
                : null
            }
            domains={domains.map((d) => ({
              id: d.id,
              domain: d.domain,
              status: d.status,
              isParentCompany: d.isParentCompany,
              checkedAt: d.checkedAt?.toISOString() ?? null,
              allLeadCount: d.allLeadCount ?? null,
              verifiedEmployeeCount: d.verifiedEmployeeCount,
              revenue: d.revenue,
              parentId: d.parentId,
              parentPending: d.parentPending,
              parentDomain: d.parentDomain,
              parentCampaignId: d.parentCampaignId,
              parentPreviouslyAdded:
                Boolean(d.parentDomain && d.parentCampaignId && d.parentCampaignId !== campaign.id),
              reason: d.reason,
              qualificationDebug: d.qualificationDebug,
            }))}
          />
        </div>
      </div>
    </div>
  );
}
