import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { getAiLeadDetail, parseUpdateAiLeadRequest, updateAiLead } from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

type Params = { params: Promise<{ id: string; contactId: string }> };

/** One lead with the activity of its person: every call and WhatsApp message, newest first. */
export async function GET(request: NextRequest, { params }: Params) {
  try {
    const { id, contactId } = await params;
    return await withOrgContext(request, async () => Response.json(await getAiLeadDetail(id, contactId)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

/** `{ action: "stop" }`, `{ action: "requeue" }` (a failed, unreached or hand-stopped lead), or `{ instructions }` (the lead's own). */
export async function PATCH(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id, contactId } = await params;
    const body = parseUpdateAiLeadRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json({ lead: await updateAiLead(id, contactId, body, ctx.userName) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
