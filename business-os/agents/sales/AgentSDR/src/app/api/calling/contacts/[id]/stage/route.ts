import type { NextRequest } from "next/server";
import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseCategoryKey,
  parseUuid,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import type { SetLeadStageRequest } from "@/lib/calls/contract";
import { callApiErrorResponse, loadCampaignContact } from "@/lib/calls/campaigns";
import { setLeadStage } from "@/lib/calls/leadStage";
import { runInOrganization } from "@/lib/tenancy/scope";

function parseSetLeadStageRequest(value: unknown): SetLeadStageRequest {
  assertObject(value);
  assertExactKeys(value, ["categoryKey", "subcategoryId"]);
  if (value.subcategoryId === undefined) {
    throw new CrmConfigurationValidationError("subcategoryId is required (null sets the category alone)");
  }
  return {
    // The four fixed categories are exactly LEAD_STAGE_CATEGORIES.
    categoryKey: parseCategoryKey(value.categoryKey),
    subcategoryId: value.subcategoryId === null ? null : parseUuid(value.subcategoryId, "subcategoryId"),
  };
}

// Sets the lead's CRM stage by hand — the same stage email and LinkedIn use —
// creating their CRM record if they have none. Responds with the contact.
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseSetLeadStageRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => {
      await setLeadStage(id, body);
      return Response.json(await loadCampaignContact(id));
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
