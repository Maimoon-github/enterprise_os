import CreateCampaignForm from "@/components/campaigns/CreateCampaignForm";
import CampaignListClient from "@/components/campaigns/CampaignListClient";
import { requirePageOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { listCampaigns } from "@/lib/qualification";

export const dynamic = "force-dynamic";

export default async function CampaignsPage() {
  const ctx = await requirePageOrgContext();
  const campaigns = await runInOrganization(ctx.organizationId, () => listCampaigns());

  return (
    <div className="h-full flex overflow-hidden bg-bg-weak-50">
      <div className="flex-1 flex min-w-0 overflow-hidden">
        {/* Create form — left */}
        <aside className="w-80 shrink-0 border-r border-stroke-soft-200 bg-bg-white-0 overflow-y-auto">
          <div className="px-4 py-4 border-b border-stroke-soft-200">
            <h1 className="text-sm font-bold text-text-strong-950">New Campaign</h1>
            <p className="text-xs text-text-strong-950/60 mt-0.5">Qualify brands &amp; build an Apollo list</p>
          </div>
          <CreateCampaignForm />
        </aside>

        {/* Campaign list — right */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div className="px-6 py-5 overflow-y-auto">
            <h2 className="text-lg font-bold text-text-strong-950 mb-4">Campaigns</h2>
            <CampaignListClient campaigns={campaigns} />
          </div>
        </div>
      </div>
    </div>
  );
}
