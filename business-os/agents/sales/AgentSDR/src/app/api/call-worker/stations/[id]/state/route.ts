import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, parseWorkerStationStateRequest, reportStationState } from "@/lib/calls/stations";

/** The worker's report on a station: logged in or out, and the link screen while linking. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = parseWorkerStationStateRequest(await request.json().catch(() => null));
    await reportStationState((await params).id, body);
    return Response.json({ ok: true });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
