import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, leaseStations, parseLeaseRequest } from "@/lib/calls/stations";

/**
 * The call worker renews the numbers it keeps WhatsApp Web open for, and is
 * granted more (services/call-worker, openStations.ts). Public in proxy.ts
 * under /api/call-worker/; authorizeWorker is the auth check.
 */
export async function POST(request: Request) {
  try {
    authorizeWorker(request);
    return Response.json(await leaseStations(parseLeaseRequest(await request.json().catch(() => null))));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
