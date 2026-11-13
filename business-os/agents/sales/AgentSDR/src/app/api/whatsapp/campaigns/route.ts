import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { createWhatsappCampaign, listWhatsappCampaigns } from "@/lib/whatsapp/campaigns/campaigns.server";
import type { ListWhatsappCampaignsResponse } from "@/lib/whatsapp/campaigns/contract";
import { parseCreateRequest } from "./parse";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () =>
      Response.json({ campaigns: await listWhatsappCampaigns() } satisfies ListWhatsappCampaignsResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}

/** Always created paused; launching is a PATCH with status "active". */
export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseCreateRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json(await createWhatsappCampaign(body), { status: 201 }));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
