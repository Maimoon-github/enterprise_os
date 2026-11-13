import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { whatsappCampaignMergeFields } from "@/lib/whatsapp/campaigns/campaigns.server";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    return await withOrgContext(request, async () => Response.json(await whatsappCampaignMergeFields(id)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
