import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { resolveCrmIdentityException } from "@/lib/crm/identity";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["status", "personId"]);
      if (value.status !== "resolved" && value.status !== "ignored") throw new Error("status must be resolved or ignored");
      return Response.json({ exception: await resolveCrmIdentityException({
        id: parseUuid((await params).id, "identity exception id"),
        status: value.status,
        personId: value.personId == null ? null : parseUuid(value.personId, "personId"),
      }) });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
