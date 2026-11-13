import { NextRequest, NextResponse } from "next/server";
import { getCampaign, getLead, getLeadEmails } from "@/lib/outreach/campaigns";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// GET /api/outreach/campaigns/[id]/leads/[leadId] — lead + its sequence email
// history, for the activity side panel. The campaign's sequence ships too: the
// panel's Sequence tab shows steps the lead has not reached yet, and those have
// no outreach_emails row to read a subject from (rows are written at send time).
export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string; leadId: string }> }) {
  try {
    return await withOrgContext(_req, async () => {
      const { id, leadId } = await params;
      const lead = await getLead(leadId);
      if (!lead || lead.campaignId !== id) return NextResponse.json({ error: "not found" }, { status: 404 });

      const [emails, campaign] = await Promise.all([getLeadEmails(leadId), getCampaign(id)]);
      return NextResponse.json({ lead, emails, sequence: campaign?.sequence ?? [] });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
