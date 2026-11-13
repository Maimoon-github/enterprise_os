import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { parseUuid } from "@/lib/crm/categories";
import { discardDraft } from "@/lib/crm/drafts";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      return Response.json({ draft: await discardDraft({ draftId: parseUuid((await params).id, "draft id") }) });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
