import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { mintAgentToken, parseAgentTokenRequest } from "@/lib/calls/liveAgent";
import { callApiErrorResponse, withRecorderScope } from "@/lib/calls/sessions";

/**
 * A Gemini Live token for the AI voice agent on this call (trial). Called by
 * the recorder extension's service worker with the per-call bearer token,
 * like the rest of this prefix (see the started/ route's comment).
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => {
      const body = parseAgentTokenRequest(await readCrmJson(request));
      return Response.json(await mintAgentToken(row, body));
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
