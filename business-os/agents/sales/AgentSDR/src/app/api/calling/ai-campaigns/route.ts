import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { createAiCampaign, listAiCampaigns, parseCreateAiCampaignRequest } from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => Response.json({ campaigns: await listAiCampaigns() }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseCreateAiCampaignRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await createAiCampaign(body), { status: 201 }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
