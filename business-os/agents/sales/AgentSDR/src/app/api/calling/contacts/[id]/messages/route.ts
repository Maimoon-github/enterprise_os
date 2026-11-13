import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, parseRequiredText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, logCallMessage } from "@/lib/calls/campaigns";
import type { LogCallMessageRequest } from "@/lib/calls/contract";
import { runInOrganization } from "@/lib/tenancy/scope";

function parseLogCallMessageRequest(value: unknown): LogCallMessageRequest {
  assertObject(value);
  assertExactKeys(value, ["body", "callId"]);
  return {
    body: parseRequiredText(value.body, "body", 4000),
    callId: value.callId === undefined ? undefined : value.callId === null ? null : parseUuid(value.callId, "callId"),
  };
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = parseLogCallMessageRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await logCallMessage(id, body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
