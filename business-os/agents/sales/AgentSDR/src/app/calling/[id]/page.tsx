import { redirect } from "next/navigation";

// Campaigns lived at /calling/:id before WhatsApp Calling had its own
// Overview; keep old links working.
export default async function OldCallingCampaignPage({ params }: { params: Promise<{ id: string }> }) {
  redirect(`/calling/campaigns/${encodeURIComponent((await params).id)}`);
}
