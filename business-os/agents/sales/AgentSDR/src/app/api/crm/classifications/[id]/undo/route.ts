import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { parseUuid } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { undoClassification } from "@/lib/crm/operations";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const classificationId = parseUuid((await params).id, "classification id");
      return Response.json({ record: await undoClassification({ classificationId }) });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
