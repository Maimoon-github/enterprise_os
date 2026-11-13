import type { NextRequest } from "next/server";
import { crmOperationErrorResponse, requireInteger } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { assignSequenceToRecord } from "@/lib/crm/operations";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["sequenceId", "conversationId", "expectedContextVersion", "startStepPosition"]);
      const result = await assignSequenceToRecord({
        recordId: parseUuid((await params).id, "record id"),
        sequenceId: parseUuid(value.sequenceId, "sequenceId"),
        conversationId: parseUuid(value.conversationId, "conversationId"),
        expectedContextVersion: requireInteger(value.expectedContextVersion, "expectedContextVersion"),
        startStepPosition: value.startStepPosition === undefined ? undefined : requireInteger(value.startStepPosition, "startStepPosition"),
      });
      return Response.json(result);
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
