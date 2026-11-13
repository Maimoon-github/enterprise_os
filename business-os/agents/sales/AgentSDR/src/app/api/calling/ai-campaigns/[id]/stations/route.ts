import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { parseStationIds, setAiCampaignStations } from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

/** Replaces the calling numbers the campaign places its calls and messages from. */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    const stationIds = parseStationIds(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await setAiCampaignStations(id, stationIds)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
