import { requirePageOrgContext } from "@/lib/auth/context";
import { WhatsappCampaignDetailClient, type CampaignTab } from "@/components/whatsapp/campaigns/WhatsappCampaignDetailClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Message campaign" };

export default async function WhatsappCampaignPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  await requirePageOrgContext();
  const [{ id }, { tab }] = await Promise.all([params, searchParams]);
  const initialTab: CampaignTab = tab === "leads" || tab === "sequence" ? tab : "overview";
  return <WhatsappCampaignDetailClient campaignId={id} initialTab={initialTab} />;
}
