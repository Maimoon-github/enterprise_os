import { authorizeWorker } from "@/lib/calls/stations";
import { claimStationMessageJob, stationWorkerErrorResponse } from "@/lib/whatsapp/stationMessaging";
import { parseMessageClaim } from "@/lib/whatsapp/stationParse";

/**
 * The call worker asks for the next WhatsApp message to send from one of the
 * numbers it holds open (src/lib/whatsapp/stationMessaging.ts). Public in
 * proxy.ts under /api/call-worker/; authorizeWorker is the auth check.
 */
export async function POST(request: Request) {
  try {
    authorizeWorker(request);
    const body = parseMessageClaim(await request.json().catch(() => null));
    return Response.json({ job: await claimStationMessageJob(body) });
  } catch (error) {
    return stationWorkerErrorResponse(error);
  }
}
