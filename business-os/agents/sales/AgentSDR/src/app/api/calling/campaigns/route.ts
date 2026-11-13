import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, createCampaign, listCampaigns } from "@/lib/calls/campaigns";
import type { CreateCampaignRequest } from "@/lib/calls/contract";
import { runInOrganization } from "@/lib/tenancy/scope";
import { withOrgContext } from "@/lib/auth/context";

function parseCreateCampaignRequest(value: unknown): CreateCampaignRequest {
  assertObject(value);
  assertExactKeys(value, ["name", "description"]);
  return {
    name: parseRequiredText(value.name, "name", 120),
    description: parseOptionalText(value.description, "description", 2000) ?? null,
  };
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseCreateCampaignRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await createCampaign(body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

// Proxy-gated GET, like /api/calls's GET — no requireCrmMutationContext here.
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => Response.json({ campaigns: await listCampaigns() }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
