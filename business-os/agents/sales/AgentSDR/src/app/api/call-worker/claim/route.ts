import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, claimWorkerJob, parseWorkerClaimRequest } from "@/lib/calls/stations";

/**
 * The cloud call worker asks for its next job (services/call-worker). Public
 * in proxy.ts; authorizeWorker is the auth check. Claims across every
 * organization — each job names the organization it belongs to.
 */
export async function POST(request: Request) {
  try {
    authorizeWorker(request);
    const body = parseWorkerClaimRequest(await request.json().catch(() => null));
    return Response.json({ job: await claimWorkerJob(body) });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
