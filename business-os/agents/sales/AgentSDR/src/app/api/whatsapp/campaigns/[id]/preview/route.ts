import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, CrmConfigurationValidationError, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { previewWhatsappCampaignStep } from "@/lib/whatsapp/campaigns/campaigns.server";
import type { PreviewWhatsappCampaignStepRequest } from "@/lib/whatsapp/campaigns/contract";

/** POST, not GET: the body is a message draft. The first lead is used when no leadId is given. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    const body = await readCrmJson(request);
    assertObject(body);
    assertExactKeys(body, ["body", "leadId"]);
    if (typeof body.body !== "string") throw new CrmConfigurationValidationError("body must be a string");
    if (body.body.length > 20000) throw new CrmConfigurationValidationError("body is too long");
    if (body.leadId !== undefined && body.leadId !== null && typeof body.leadId !== "string") {
      throw new CrmConfigurationValidationError("leadId must be a string");
    }
    const input: PreviewWhatsappCampaignStepRequest = { body: body.body, leadId: body.leadId ?? undefined };
    return await runInOrganization(ctx.organizationId, async () => Response.json(await previewWhatsappCampaignStep(id, input)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
