import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, updateCampaignContactPerson } from "@/lib/calls/campaigns";
import type { UpdateCampaignContactPersonRequest } from "@/lib/calls/contract";
import { runInOrganization } from "@/lib/tenancy/scope";

function parseUpdateCampaignContactPersonRequest(value: unknown): UpdateCampaignContactPersonRequest {
  assertObject(value);
  assertExactKeys(value, ["fullName", "phone", "companyName", "companyWebsite", "title", "email", "profilePictureUrl"]);
  return {
    fullName: value.fullName === undefined ? undefined : parseRequiredText(value.fullName, "fullName", 200),
    phone: value.phone === undefined ? undefined : parseRequiredText(value.phone, "phone", 40),
    companyName: parseOptionalText(value.companyName, "companyName", 200),
    companyWebsite: parseOptionalText(value.companyWebsite, "companyWebsite", 500),
    title: parseOptionalText(value.title, "title", 200),
    email: parseOptionalText(value.email, "email", 320),
    profilePictureUrl: parseOptionalText(value.profilePictureUrl, "profilePictureUrl", 2000),
  };
}

// Edits the People record behind a campaign contact — shared across
// AgentSDR, not a campaign-local copy. Only the keys given change.
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseUpdateCampaignContactPersonRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await updateCampaignContactPerson(id, body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
