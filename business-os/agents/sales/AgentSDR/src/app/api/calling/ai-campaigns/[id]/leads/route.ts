import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { addPeopleToAiCampaign, listAiLeads, parseAiLeadsQuery, parsePersonIds } from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

type Params = { params: Promise<{ id: string }> };

export async function GET(request: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    const query = parseAiLeadsQuery(new URL(request.url));
    return await withOrgContext(request, async () => Response.json(await listAiLeads(id, query)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

/** Adds People (with a phone number) to the campaign; the shared "Add from People" picker posts here. */
export async function POST(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    const personIds = parsePersonIds(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await addPeopleToAiCampaign(id, personIds)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
