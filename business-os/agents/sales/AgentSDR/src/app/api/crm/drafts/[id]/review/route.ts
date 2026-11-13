import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { takeOverAutoFollowUp } from "@/lib/crm/autoFollowUps";
import { parseUuid } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";

/**
 * "Review before sending": takes an automatic follow-up off the sender and
 * puts it in Action required like any other draft. `taken` is false when it
 * was not (or no longer) waiting to send on its own.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const taken = await takeOverAutoFollowUp({ draftId: parseUuid((await params).id, "draft id") });
      return Response.json({ taken });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
