import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { deleteStation, parseUpdateStationRequest, updateStation } from "@/lib/calls/stations";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseUpdateStationRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json({ station: await updateStation(id, body) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => {
      await deleteStation(id);
      return Response.json({ ok: true });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
