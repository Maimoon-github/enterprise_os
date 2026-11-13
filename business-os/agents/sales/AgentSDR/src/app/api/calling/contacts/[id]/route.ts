import type { NextRequest } from "next/server";
import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseOptionalText,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import {
  CAMPAIGN_CONTACT_STAGES,
  CONTACT_CALL_STATUS_DEFINITIONS,
  type CampaignContactStage,
  type ContactCallStatus,
  type UpdateCampaignContactRequest,
} from "@/lib/calls/contract";
import { callApiErrorResponse, getCampaignContactDetail, removeCampaignContact, updateCampaignContact } from "@/lib/calls/campaigns";
import { parseOptionalIsoTimestamp } from "@/lib/calls/sessions";
import { runInOrganization } from "@/lib/tenancy/scope";
import { withOrgContext } from "@/lib/auth/context";

/** Only the statuses a rep may set; "calling", "failed" and "not called" come from calls alone. */
function parseManualCallStatus(value: unknown): ContactCallStatus {
  if (
    typeof value !== "string" ||
    !Object.hasOwn(CONTACT_CALL_STATUS_DEFINITIONS, value) ||
    !CONTACT_CALL_STATUS_DEFINITIONS[value as ContactCallStatus].manual
  ) {
    throw new CrmConfigurationValidationError(
      "callStatus must be one of: no_answer, busy, connected, not_on_whatsapp, wrong_number",
    );
  }
  return value as ContactCallStatus;
}

function parseStage(value: unknown): CampaignContactStage {
  if (typeof value !== "string" || !(CAMPAIGN_CONTACT_STAGES as readonly string[]).includes(value)) {
    throw new CrmConfigurationValidationError("stage must be one of: to_call, follow_up, done");
  }
  return value as CampaignContactStage;
}

function parseUpdateCampaignContactRequest(value: unknown): UpdateCampaignContactRequest {
  assertObject(value);
  assertExactKeys(value, ["callStatus", "stage", "followUpAt", "notes"]);
  return {
    callStatus: value.callStatus === undefined ? undefined : parseManualCallStatus(value.callStatus),
    stage: value.stage === undefined ? undefined : parseStage(value.stage),
    followUpAt: parseOptionalIsoTimestamp(value.followUpAt, "followUpAt"),
    notes: parseOptionalText(value.notes, "notes", 4000),
  };
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = (await params).id;
    return await withOrgContext(request, async () => Response.json(await getCampaignContactDetail(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseUpdateCampaignContactRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await updateCampaignContact(id, body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

// Takes the person off the campaign; the person, their calls and recordings
// stay.
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => {
      await removeCampaignContact(id);
      return Response.json({ ok: true });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
