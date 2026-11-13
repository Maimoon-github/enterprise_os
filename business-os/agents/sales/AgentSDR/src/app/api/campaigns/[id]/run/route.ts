import { NextRequest, NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { inOrg } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { campaigns } from "@/lib/schema";
import { recoverStaleJobs, startCampaignJob } from "@/lib/qualification/jobRunner";

// POST /api/campaigns/[id]/run — run a qualification job for the campaign.
//   body: { limit? }  (max candidates to pull this run, "leads" mode only; default 500)
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    return await withOrgContext(req, () => run(req, id));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function run(req: NextRequest, id: string) {
  let limit = 500;
  try {
    const body = await req.json();
    if (typeof body?.limit === "number") limit = body.limit;
  } catch {
    // no body — use default
  }

  const [campaign] = await db
    .select()
    .from(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, id)))
    .limit(1);
  if (!campaign) {
    return NextResponse.json({ error: "campaign not found" }, { status: 404 });
  }

  // "domains" mode's batch size is fixed at campaign creation (targetDomainCount)
  // — jobRunner ignores requestedLimit for that mode, so no override needed here.

  try {
    await recoverStaleJobs();
    const job = await startCampaignJob(id, Math.min(Math.max(limit, 1), 1000));
    return NextResponse.json({ job, started: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "job failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
