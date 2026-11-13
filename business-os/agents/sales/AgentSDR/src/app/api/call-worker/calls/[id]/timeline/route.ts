import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, parseTimelineRequest, saveCallTimeline } from "@/lib/calls/stations";

/** The call worker's record of a cloud call's timed steps (its own and the extension's); replaces the stored one. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const entries = parseTimelineRequest(await request.json().catch(() => null));
    await saveCallTimeline((await params).id, entries);
    return Response.json({ ok: true });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
