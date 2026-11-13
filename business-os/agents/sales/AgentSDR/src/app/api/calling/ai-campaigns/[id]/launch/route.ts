import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { launchAiCampaign } from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

/** Validates the campaign and starts it: from now the AI agent places its calls. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    return await runInOrganization(ctx.organizationId, async () => Response.json(await launchAiCampaign(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
