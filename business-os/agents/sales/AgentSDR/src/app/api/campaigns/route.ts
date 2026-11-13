import { NextRequest, NextResponse } from "next/server";
import { desc } from "drizzle-orm";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { inOrg } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { campaigns } from "@/lib/schema";
import {
  createCampaign,
  lookupManualDomains,
  addManualCandidates,
} from "@/lib/qualification";
import type { CampaignFilters, CampaignInputMode, CampaignTargetMode } from "@/lib/qualification";

// GET /api/campaigns — list campaigns (most recent first).
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const rows = await db
        .select()
        .from(campaigns)
        .where(inOrg(campaigns))
        .orderBy(desc(campaigns.createdAt))
        .limit(100);
      return NextResponse.json({ campaigns: rows });
    });
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

// POST /api/campaigns — create a campaign in either mode.
//   filters mode: { inputMode:"filters", jobTitles[], targetMode?, targetLeadCount?, targetDomainCount?, filters }
//   manual mode:  { inputMode:"manual",  jobTitles[], targetMode?, targetLeadCount?, targetDomainCount?, domains[] }
export async function POST(req: NextRequest) {
  try {
    return await withOrgContext(req, () => create(req));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function create(req: NextRequest) {
  let body: {
    name?: string;
    inputMode?: CampaignInputMode;
    jobTitles?: string[];
    targetMode?: CampaignTargetMode;
    targetLeadCount?: number;
    targetDomainCount?: number;
    filters?: CampaignFilters;
    domains?: string[];
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  if (!body.inputMode) {
    return NextResponse.json({ error: "inputMode is required" }, { status: 400 });
  }
  const jobTitles = body.jobTitles ?? [];

  const campaign = await createCampaign({
    name: body.name,
    inputMode: body.inputMode,
    jobTitles,
    targetMode: body.targetMode,
    targetLeadCount: body.targetLeadCount,
    targetDomainCount: body.targetDomainCount,
    filters: body.inputMode === "filters" ? body.filters : undefined,
  });

  // Manual mode: validate the pasted domains against the DB and stage them.
  if (body.inputMode === "manual") {
    const lookup = await lookupManualDomains(body.domains ?? []);
    const staged = await addManualCandidates(campaign.id, lookup.found);
    return NextResponse.json({ campaign, lookup, staged }, { status: 201 });
  }

  return NextResponse.json({ campaign }, { status: 201 });
}
