import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { inOrg } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { campaigns } from "@/lib/schema";
import { getCampaignDomains, assembleApolloLink } from "@/lib/qualification";

// GET /api/campaigns/[id]/output — the campaign deliverable:
//   the Apollo link of all qualified domains + the per-domain status table.
export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    return await withOrgContext(req, () => output(id));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function output(id: string) {

  const [campaign] = await db
    .select()
    .from(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, id)))
    .limit(1);
  if (!campaign) {
    return NextResponse.json({ error: "campaign not found" }, { status: 404 });
  }

  const domainsTable = await getCampaignDomains(id);
  // Refresh the link from the current qualified set.
  const apolloLink = await assembleApolloLink(id);

  const qualified = domainsTable.filter((d) => d.status === "qualified");

  return NextResponse.json({
    campaign: { ...campaign, apolloLink },
    apolloLink,
    counts: {
      total: domainsTable.length,
      qualified: qualified.length,
    },
    domains: domainsTable,
  });
}
