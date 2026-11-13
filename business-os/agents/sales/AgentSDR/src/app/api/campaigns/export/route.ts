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

// GET /api/campaigns/export?ids=id1,id2,id3 — one combined CSV of targeted
// domains across multiple campaigns, with a leading "Campaign" column.
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, () => exportCampaigns(req));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function exportCampaigns(req: NextRequest) {
  const idsParam = req.nextUrl.searchParams.get("ids") ?? "";
  const ids = [...new Set(idsParam.split(",").map((id) => id.trim()).filter(Boolean))];

  if (ids.length === 0) {
    return NextResponse.json({ error: "no campaign ids provided" }, { status: 400 });
  }

  const headers = [
    "Campaign", "Domain", "Status", "Timestamp", "Is Parent Company", "Revenue",
    "All Leads", "Verified Leads", "Parent Domain", "Parent Pending", "Reason",
  ];
  const csvRows = [headers.join(",")];
  let totalRows = 0;

  for (const id of ids) {
    const campaign = await getCampaign(id);
    if (!campaign) continue;

    const rows = await getCampaignDomains(id);
    totalRows += rows.length;

    for (const r of rows) {
      csvRows.push(
        [
          csvEscape(campaign.name),
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
      );
    }
  }

  const csv = csvRows.join("\n");
  const filename = `campaigns-${ids.length}-${totalRows}rows.csv`;

  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
