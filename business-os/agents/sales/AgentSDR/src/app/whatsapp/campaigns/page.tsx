import { requirePageOrgContext } from "@/lib/auth/context";
import { WhatsappCampaignsClient } from "@/components/whatsapp/campaigns/WhatsappCampaignsClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Message campaigns" };

export default async function WhatsappCampaignsPage() {
  await requirePageOrgContext();
  return <WhatsappCampaignsClient />;
}
