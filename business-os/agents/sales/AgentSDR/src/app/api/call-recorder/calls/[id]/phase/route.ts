import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { callApiErrorResponse, withRecorderScope } from "@/lib/calls/sessions";
import { parsePhaseRequest, recordPhase } from "@/lib/calls/stations";

/**
 * A cloud call's phase, from the extension in station mode — the rep's page
 * polls it, since no AgentSDR tab sits beside the cloud browser to hear it.
 * Bearer-token authorized like the rest of this prefix.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => {
      await recordPhase(row, parsePhaseRequest(await readCrmJson(request)));
      return Response.json({ ok: true });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
