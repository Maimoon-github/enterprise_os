import type { NextRequest } from "next/server";
import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseOptionalText,
  parseRequiredText,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { archiveCampaign, callApiErrorResponse, getCampaignDetail, updateCampaign } from "@/lib/calls/campaigns";
import { CALL_CAMPAIGN_STATUSES, type CallCampaignStatus, type UpdateCampaignRequest } from "@/lib/calls/contract";
import { runInOrganization } from "@/lib/tenancy/scope";
import { withOrgContext } from "@/lib/auth/context";

function parseStatus(value: unknown): CallCampaignStatus {
  if (typeof value !== "string" || !(CALL_CAMPAIGN_STATUSES as readonly string[]).includes(value)) {
    throw new CrmConfigurationValidationError("status must be one of: active, paused");
  }
  return value as CallCampaignStatus;
}

function parseUpdateCampaignRequest(value: unknown): UpdateCampaignRequest {
  assertObject(value);
  assertExactKeys(value, ["name", "description", "status"]);
  return {
    name: value.name === undefined ? undefined : parseRequiredText(value.name, "name", 120),
    description: parseOptionalText(value.description, "description", 1000),
    status: value.status === undefined ? undefined : parseStatus(value.status),
  };
}

// getCampaignDetail 404s on a malformed id itself (see campaigns.ts's
// assertUuidShape) — no separate parseUuid here.
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = (await params).id;
    return await withOrgContext(request, async () => Response.json(await getCampaignDetail(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseUpdateCampaignRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await updateCampaign(id, body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

// Archives the campaign (archived_at): it leaves the Calling section, but
// its contacts' calls, recordings and transcripts stay on the people they
// belong to.
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => {
      await archiveCampaign(id);
      return Response.json({ ok: true });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
