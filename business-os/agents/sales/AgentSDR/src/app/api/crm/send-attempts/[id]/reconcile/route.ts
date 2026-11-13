import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { reconcileDeliveryUncertain } from "@/lib/crm/send";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["delivered", "providerMessageId", "note"]);
      if (typeof value.delivered !== "boolean") throw new Error("delivered must be a boolean");
      const attempt = await reconcileDeliveryUncertain({
        attemptId: parseUuid((await params).id, "send attempt id"),
        delivered: value.delivered,
        providerMessageId: parseOptionalText(value.providerMessageId, "providerMessageId", 1_000),
        note: parseRequiredText(value.note, "note", 2_000),
      });
      return Response.json({ attempt });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
