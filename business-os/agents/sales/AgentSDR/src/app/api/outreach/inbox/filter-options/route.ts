import { NextRequest, NextResponse } from "next/server";
import { searchInboxLeads, listInboxAccounts, listInboxStatuses } from "@/lib/inbox/queries";
import { listCampaigns } from "@/lib/outreach/campaigns";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// GET /api/outreach/inbox/filter-options?leadQuery=
// Bundles everything the filter panel needs: leads (search-scoped),
// campaigns, accounts (mailbox addresses), and status configs.
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const leadQuery = req.nextUrl.searchParams.get("leadQuery") ?? "";

      const [leads, campaigns, accounts, statusConfigs] = await Promise.all([
        searchInboxLeads(leadQuery),
        listCampaigns(),
        listInboxAccounts(),
        listInboxStatuses(),
      ]);

      return NextResponse.json({
        leads,
        campaigns: campaigns.map((c) => ({ id: c.id, name: c.name })),
        accounts,
        statuses: statusConfigs.map((s) => ({ statusKey: s.statusKey, label: s.label, statusGroup: s.statusGroup })),
      });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
