import { authorizeWorker } from "@/lib/calls/stations";
import { reportStationMessageResult, stationWorkerErrorResponse } from "@/lib/whatsapp/stationMessaging";
import { parseMessageResult } from "@/lib/whatsapp/stationParse";

/** The call worker's report on a message it was given: sent (with WhatsApp's id, when read), or why not. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = parseMessageResult(await request.json().catch(() => null));
    await reportStationMessageResult((await params).id, body);
    return Response.json({ ok: true });
  } catch (error) {
    return stationWorkerErrorResponse(error);
  }
}
