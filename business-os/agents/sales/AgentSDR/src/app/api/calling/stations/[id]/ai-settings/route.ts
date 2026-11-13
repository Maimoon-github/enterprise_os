import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { parseStationAiSettings, updateStationAiSettings } from "@/lib/calls/stationSettings";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseStationAiSettings(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json({ settings: await updateStationAiSettings(id, body) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
