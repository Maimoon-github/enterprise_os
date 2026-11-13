import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { rehearseAgent, type RehearsalTurn } from "@/lib/calls/liveAgent";
import { resolveRehearsal } from "@/lib/calls/rehearsal";
import { CallApiError, callApiErrorResponse } from "@/lib/calls/sessions";

const MAX_TURNS = 40;
const MAX_TURN_CHARS = 1_000;

/**
 * POST /api/calling/agent/rehearse — type as the lead and read what the AI
 * agent says, with the exact prompt a campaign call would get. Costs one
 * Gemini Live turn per request; the conversation lives in the browser.
 */
export async function POST(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
      if (!body || typeof body !== "object") throw new CallApiError(400, "Expected a JSON object");
      const turns = parseTurns(body.turns);
      const { request: agentRequest, knowledge, context } = await resolveRehearsal(body);
      const result = await rehearseAgent(agentRequest, knowledge, context, turns);
      return Response.json(result);
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

function parseTurns(value: unknown): RehearsalTurn[] {
  if (!Array.isArray(value)) throw new CallApiError(400, "turns must be a list");
  if (value.length > MAX_TURNS) throw new CallApiError(400, `At most ${MAX_TURNS} turns`);
  return value.map((raw) => {
    const turn = raw as { role?: unknown; text?: unknown } | null;
    if (!turn || (turn.role !== "lead" && turn.role !== "agent") || typeof turn.text !== "string" || !turn.text.trim()) {
      throw new CallApiError(400, "Each turn needs a role (lead or agent) and text");
    }
    return { role: turn.role, text: turn.text.trim().slice(0, MAX_TURN_CHARS) };
  });
}
