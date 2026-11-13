import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { createManualDraft } from "@/lib/crm/operations";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["conversationId", "subject", "bodyText", "bodyHtml"]);
      const draft = await createManualDraft({
        recordId: parseUuid((await params).id, "record id"),
        conversationId: parseUuid(value.conversationId, "conversationId"),
        subject: parseOptionalText(value.subject, "subject", 998),
        bodyText: parseRequiredText(value.bodyText, "bodyText", 100_000),
        bodyHtml: parseOptionalText(value.bodyHtml, "bodyHtml", 100_000),
      });
      return Response.json({ draft }, { status: 201 });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
