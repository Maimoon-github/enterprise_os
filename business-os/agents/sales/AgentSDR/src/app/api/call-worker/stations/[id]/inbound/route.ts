import { authorizeWorker } from "@/lib/calls/stations";
import { ingestStationMessages } from "@/lib/whatsapp/messages";
import { stationWorkerErrorResponse } from "@/lib/whatsapp/stationMessaging";
import { parseInboundRequest } from "@/lib/whatsapp/stationParse";

/**
 * What a station's WhatsApp Web showed arriving on its number (the leads'
 * messages, and what was sent from the phone), as the call worker read it
 * from the extension. Stored like Unipile's WhatsApp messages, CRM included.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = parseInboundRequest(await request.json().catch(() => null));
    return Response.json(await ingestStationMessages((await params).id, body.messages));
  } catch (error) {
    return stationWorkerErrorResponse(error);
  }
}
