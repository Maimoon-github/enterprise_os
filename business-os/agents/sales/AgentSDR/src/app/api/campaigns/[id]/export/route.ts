import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { getCampaign, getCampaignDomains } from "@/lib/qualification";

export const dynamic = "force-dynamic";

function csvEscape(val: string | number | boolean | null | undefined): string {
  if (val === null || val === undefined) return "";
  const s = String(val);
  if (s.includes('"') || s.includes(",") || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

// GET /api/campaigns/[id]/export — CSV of this campaign's targeted domains.
export async function GET(
  req: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  try {
    return await withOrgContext(req, () => exportCampaign(context));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function exportCampaign({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const campaign = await getCampaign(id);
  if (!campaign) {
    return NextResponse.json({ error: "campaign not found" }, { status: 404 });
  }

  const rows = await getCampaignDomains(id);

  const headers = [
    "Domain", "Status", "Timestamp", "Is Parent Company", "Revenue",
    "All Leads", "Verified Leads", "Parent Domain", "Parent Pending", "Reason",
  ];

  const csvRows = [
    headers.join(","),
    ...rows.map((r) =>
      [
        csvEscape(r.domain),
        csvEscape(r.status),
        csvEscape(r.checkedAt?.toISOString() ?? null),
        csvEscape(r.isParentCompany),
        csvEscape(r.revenue !== null ? Number(r.revenue) : null),
        csvEscape(r.allLeadCount),
        csvEscape(r.verifiedEmployeeCount),
        csvEscape(r.parentDomain),
        csvEscape(r.parentPending),
        csvEscape(r.reason),
      ].join(","),
    ),
  ];

  const csv = csvRows.join("\n");

  const slug = campaign.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const filename = `campaign-${slug || id}-${rows.length}rows.csv`;

  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
