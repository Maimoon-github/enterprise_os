import { authorizeWorker } from "@/lib/calls/stations";
import { decideIncomingCall } from "@/lib/calls/incoming";
import { parseIncomingCallRequest } from "@/lib/whatsapp/stationParse";
import { stationWorkerErrorResponse } from "@/lib/whatsapp/stationMessaging";

/**
 * A WhatsApp call is ringing on a station's number: whether the AI agent
 * answers it, and with which call (src/lib/calls/incoming.ts).
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = parseIncomingCallRequest(await request.json().catch(() => null));
    return Response.json(await decideIncomingCall((await params).id, body));
  } catch (error) {
    return stationWorkerErrorResponse(error);
  }
}
