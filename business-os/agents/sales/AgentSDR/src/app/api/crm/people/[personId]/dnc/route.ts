import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseRequiredText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { clearPersonDoNotContact, setPersonDoNotContact } from "@/lib/crm/policies";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ personId: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const personId = parseUuid((await params).personId, "person id");
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["enabled", "reason"]);
      if (typeof value.enabled !== "boolean") throw new Error("enabled must be boolean");
      const reason = value.reason === undefined
        ? (value.enabled ? "Set by operator" : "Cleared by operator")
        : parseRequiredText(value.reason, "reason", 2_000);
      const policy = value.enabled
        ? await setPersonDoNotContact({ personId, reason, source: "human", actorType: "authenticated_operator" })
        : await clearPersonDoNotContact({ personId, reason, source: "human", actorType: "authenticated_operator" });
      return Response.json({ policy });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
