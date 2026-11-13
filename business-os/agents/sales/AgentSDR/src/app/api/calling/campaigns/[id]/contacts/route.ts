import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { addCampaignContact, callApiErrorResponse } from "@/lib/calls/campaigns";
import type { AddCampaignContactRequest } from "@/lib/calls/contract";
import { runInOrganization } from "@/lib/tenancy/scope";

function parseAddCampaignContactRequest(value: unknown): AddCampaignContactRequest {
  assertObject(value);
  assertExactKeys(value, ["fullName", "phone", "companyName", "companyWebsite", "title", "email"]);
  return {
    fullName: parseRequiredText(value.fullName, "fullName", 200),
    phone: parseRequiredText(value.phone, "phone", 40),
    companyName: parseOptionalText(value.companyName, "companyName", 200) ?? null,
    companyWebsite: parseOptionalText(value.companyWebsite, "companyWebsite", 500) ?? null,
    title: parseOptionalText(value.title, "title", 200) ?? null,
    email: parseOptionalText(value.email, "email", 320) ?? null,
  };
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const campaignId = (await params).id;
    const body = parseAddCampaignContactRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await addCampaignContact(campaignId, body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
