import type { NextRequest } from "next/server";
import { crmOperationErrorResponse, requireInteger } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseCategoryKey, parseOptionalText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { applyHumanClassification } from "@/lib/crm/operations";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["categoryKey", "subcategoryId", "expectedContextVersion", "classificationId", "reason"]);
      const result = await applyHumanClassification({
        recordId: parseUuid((await params).id, "record id"),
        categoryKey: parseCategoryKey(value.categoryKey),
        subcategoryId: value.subcategoryId === null ? null : parseUuid(value.subcategoryId, "subcategoryId"),
        expectedContextVersion: requireInteger(value.expectedContextVersion, "expectedContextVersion"),
        classificationId: value.classificationId === undefined ? undefined : parseUuid(value.classificationId, "classificationId"),
        reason: parseOptionalText(value.reason, "reason", 2_000),
      });
      return Response.json(result);
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
