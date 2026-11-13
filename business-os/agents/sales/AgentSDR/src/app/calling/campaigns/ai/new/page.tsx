import { requirePageOrgContext } from "@/lib/auth/context";
import { AiCampaignWizard } from "@/components/calling/ai/AiCampaignWizard";

export const dynamic = "force-dynamic";

export const metadata = { title: "New AI calling campaign" };

export default async function NewAiCallCampaignPage() {
  await requirePageOrgContext();
  return <AiCampaignWizard />;
}
