import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, cancelCall } from "@/lib/calls/sessions";
import { runInOrganization } from "@/lib/tenancy/scope";

/** The rep's Cancel on a call that has not connected → CallDetail. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => Response.json(await cancelCall(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
