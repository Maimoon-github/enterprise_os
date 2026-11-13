import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { getAiCampaignStats } from "@/lib/calls/aiCampaigns/campaigns.server";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    return await withOrgContext(request, async () => Response.json(await getAiCampaignStats(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
