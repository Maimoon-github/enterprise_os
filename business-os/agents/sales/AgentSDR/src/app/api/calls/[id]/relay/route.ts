import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { assertSameOriginMutation, requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, CallApiError } from "@/lib/calls/sessions";
import {
  assertProxyRules,
  isRelayUploadStream,
  readRelayPcm,
  receiveRelayUpload,
  relayStreamResponse,
  repRelayCredential,
  requireRelayableCall,
} from "@/lib/calls/remoteRep";
import { repRelay } from "@/lib/calls/repRelay.server";
import { runInOrganization } from "@/lib/tenancy/scope";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Params = { params: Promise<{ id: string }> };

/**
 * The rep's side of a call they talk on through a calling station
 * (contract.ts, "a rep talking through a calling station").
 *
 * GET — the station's audio, its presence and pings, as one long NDJSON
 * stream (RepRelayEvent per line). Accepted from the moment the call is
 * queued; a newer stream replaces this one.
 */
export async function GET(request: NextRequest, { params }: Params) {
  try {
    const id = (await params).id;
    return await withOrgContext(request, async () => {
      await requireRelayableCall(id);
      const credential = repRelayCredential(request);
      if (!credential) throw new CallApiError(401, "Sign in to continue");
      return relayStreamResponse(request, id, "rep", credential);
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

/**
 * POST — the rep's microphone (mono 16-bit LE PCM at REP_RELAY_SAMPLE_RATE)
 * for the station: as an upload stream (REP_RELAY_STREAM_HEADER), read as it
 * arrives and answered when it ends, or as one chunk (the fallback). While
 * the rep's down stream is open, the session it was opened with is enough:
 * chunks, about 25 a second, must not each cost a session and call lookup.
 */
export async function POST(request: NextRequest, { params }: Params) {
  try {
    const id = (await params).id;
    const streaming = isRelayUploadStream(request);
    if (streaming) assertProxyRules(request);
    assertSameOriginMutation(request);
    if (!repRelay().isAuthorized(id, "rep", repRelayCredential(request))) {
      const ctx = await requireCrmMutationContext(request);
      await runInOrganization(ctx.organizationId, () => requireRelayableCall(id));
    }
    if (streaming) await receiveRelayUpload(request, id, "rep");
    else repRelay().up(id, "rep", await readRelayPcm(request));
    return new Response(null, { status: 204 });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
