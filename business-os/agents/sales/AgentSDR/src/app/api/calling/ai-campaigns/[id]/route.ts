import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import {
  archiveAiCampaign,
  getAiCampaign,
  parseUpdateAiCampaignRequest,
  updateAiCampaign,
} from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

type Params = { params: Promise<{ id: string }> };

export async function GET(request: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    return await withOrgContext(request, async () => Response.json(await getAiCampaign(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function PATCH(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    const body = parseUpdateAiCampaignRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await updateAiCampaign(id, body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function DELETE(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    return await runInOrganization(ctx.organizationId, async () => {
      await archiveAiCampaign(id);
      return Response.json({ ok: true });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
