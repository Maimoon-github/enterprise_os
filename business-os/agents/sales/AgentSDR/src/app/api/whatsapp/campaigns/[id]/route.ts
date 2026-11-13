import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import {
  archiveWhatsappCampaign,
  getWhatsappCampaignDetail,
  updateWhatsappCampaign,
} from "@/lib/whatsapp/campaigns/campaigns.server";
import { parseUpdateRequest } from "../parse";

type Params = { params: Promise<{ id: string }> };

export async function GET(request: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    return await withOrgContext(request, async () => Response.json(await getWhatsappCampaignDetail(id)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}

/** Launch checks (a connected number, a lead, a first message) answer 400 with a readable message. */
export async function PATCH(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    const body = parseUpdateRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await updateWhatsappCampaign(id, body)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}

/** Archives the campaign (paused, hidden from the list); leads and history stay. */
export async function DELETE(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    return await runInOrganization(ctx.organizationId, async () => {
      await archiveWhatsappCampaign(id);
      return new Response(null, { status: 204 });
    });
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
