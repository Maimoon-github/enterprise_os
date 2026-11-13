import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, parseOptionalText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { CallApiError, callApiErrorResponse, listCalls, startCall } from "@/lib/calls/sessions";
import { parseAgentName, parseAgentVoice } from "@/lib/calls/liveAgent";
import { parseRemoteRep } from "@/lib/calls/remoteRep";
import type { StartCallRequest } from "@/lib/calls/contract";
import { runInOrganization } from "@/lib/tenancy/scope";
import { withOrgContext } from "@/lib/auth/context";

function parseStartCallRequest(value: unknown): StartCallRequest {
  assertObject(value);
  assertExactKeys(value, ["personId", "crmRecordId", "campaignContactId", "phone", "mode", "agentBrief", "agentName", "agentVoice", "stationId", "remoteRep"]);
  if (value.mode != null && value.mode !== "agent_cloud") throw new CallApiError(400, "mode must be agent_cloud");
  const remoteRep = parseRemoteRep(value.remoteRep);
  if (remoteRep && value.mode !== "agent_cloud") throw new CallApiError(400, "remoteRep needs mode agent_cloud");
  return {
    personId: parseUuid(value.personId, "personId"),
    crmRecordId: value.crmRecordId == null ? null : parseUuid(value.crmRecordId, "crmRecordId"),
    campaignContactId: value.campaignContactId == null ? null : parseUuid(value.campaignContactId, "campaignContactId"),
    phone: parseOptionalText(value.phone, "phone", 40) ?? null,
    mode: value.mode === "agent_cloud" ? "agent_cloud" : null,
    agentBrief: typeof value.agentBrief === "string" ? value.agentBrief : null,
    agentName: parseAgentName(value.agentName),
    agentVoice: parseAgentVoice(value.agentVoice),
    stationId: value.stationId == null ? null : parseUuid(value.stationId, "stationId"),
    remoteRep,
  };
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseStartCallRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () => Response.json(await startCall(body)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

// The proxy gate already authenticates GETs with the session cookie, the same
// as every other GET route under /api/crm — no requireCrmMutationContext here.
export async function GET(request: NextRequest) {
  try {
    const personId = parseUuid(request.nextUrl.searchParams.get("personId"), "personId");
    return await withOrgContext(request, async () => Response.json({ calls: await listCalls(personId) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
