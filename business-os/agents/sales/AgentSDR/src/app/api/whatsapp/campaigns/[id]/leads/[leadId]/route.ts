import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, CrmConfigurationValidationError, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { removeWhatsappCampaignLead, updateWhatsappCampaignLead } from "@/lib/whatsapp/campaigns/campaigns.server";
import type { UpdateWhatsappCampaignLeadRequest } from "@/lib/whatsapp/campaigns/contract";

type Params = { params: Promise<{ id: string; leadId: string }> };

/** stop: queued/in_sequence only. resume: stopped/failed only; 409 while a send for the step may still be in flight. */
export async function PATCH(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id, leadId } = await params;
    const body = await readCrmJson(request);
    assertObject(body);
    assertExactKeys(body, ["action"]);
    if (body.action !== "stop" && body.action !== "resume") throw new CrmConfigurationValidationError("action must be one of: stop, resume");
    const input: UpdateWhatsappCampaignLeadRequest = { action: body.action };
    return await runInOrganization(ctx.organizationId, async () => Response.json(await updateWhatsappCampaignLead(id, leadId, input)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}

export async function DELETE(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id, leadId } = await params;
    return await runInOrganization(ctx.organizationId, async () => {
      await removeWhatsappCampaignLead(id, leadId);
      return new Response(null, { status: 204 });
    });
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
