import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseOptionalText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { regenerateDraft } from "@/lib/crm/drafts";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      // `feedback` is what the reviewer wants changed. Older callers send `{}`.
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["feedback"]);
      const feedback = parseOptionalText(value.feedback, "feedback", 4_000) ?? null;
      return Response.json({ draft: await regenerateDraft(parseUuid((await params).id, "draft id"), {}, feedback) });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
