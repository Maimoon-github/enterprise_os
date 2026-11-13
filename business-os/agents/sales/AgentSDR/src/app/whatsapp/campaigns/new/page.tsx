import { requirePageOrgContext } from "@/lib/auth/context";
import { WhatsappCampaignWizard } from "@/components/whatsapp/campaigns/WhatsappCampaignWizard";

export const dynamic = "force-dynamic";

export const metadata = { title: "New message campaign" };

export default async function NewWhatsappCampaignPage() {
  await requirePageOrgContext();
  return <WhatsappCampaignWizard />;
}
