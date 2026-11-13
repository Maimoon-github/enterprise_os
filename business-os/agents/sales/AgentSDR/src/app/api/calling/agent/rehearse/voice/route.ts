import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { mintRehearsalToken } from "@/lib/calls/liveAgent";
import { resolveRehearsal } from "@/lib/calls/rehearsal";
import { CallApiError, callApiErrorResponse } from "@/lib/calls/sessions";

/**
 * POST /api/calling/agent/rehearse/voice — a rehearsal call by voice: a
 * single-use Gemini Live token with the session a campaign call would get
 * locked in (same body as …/rehearse, minus turns). The browser talks to
 * Gemini with its microphone (AgentVoiceRehearsal); no call is placed and
 * nothing is saved.
 */
export async function POST(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
      if (!body || typeof body !== "object") throw new CallApiError(400, "Expected a JSON object");
      const { request: agentRequest, knowledge, context } = await resolveRehearsal(body);
      return Response.json(await mintRehearsalToken(agentRequest, knowledge, context));
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
