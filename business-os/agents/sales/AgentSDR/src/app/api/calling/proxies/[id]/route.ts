import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { deleteProxy, parseUpdateProxyRequest, updateProxy } from "@/lib/calls/proxies";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseUpdateProxyRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json({ proxy: await updateProxy(id, body) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => {
      await deleteProxy(id);
      return Response.json({ ok: true });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
