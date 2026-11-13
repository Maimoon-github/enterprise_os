import { AiCampaignDetailClient } from "@/components/calling/ai/AiCampaignDetailClient";
import { isAiCampaignTab } from "@/components/calling/ai/tabs";

export const metadata = { title: "AI calling campaign" };

export default async function AiCallCampaignPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string | string[] }>;
}) {
  const [{ id }, { tab }] = await Promise.all([params, searchParams]);
  return <AiCampaignDetailClient campaignId={id} initialTab={isAiCampaignTab(tab) ? tab : "overview"} />;
}
