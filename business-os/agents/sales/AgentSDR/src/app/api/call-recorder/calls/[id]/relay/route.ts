import type { NextRequest } from "next/server";
import { CallApiError, callApiErrorResponse, withRecorderScope } from "@/lib/calls/sessions";
import {
  assertProxyRules,
  assertRelayable,
  isRelayUploadStream,
  readRelayPcm,
  receiveRelayUpload,
  relayStreamResponse,
  stationRelayCredential,
} from "@/lib/calls/remoteRep";
import { REP_RELAY_STREAM_HEADER } from "@/lib/calls/contract";
import { repRelay } from "@/lib/calls/repRelay.server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Params = { params: Promise<{ id: string }> };

/**
 * The station's side of a call a rep talks on through it (contract.ts, "a rep
 * talking through a calling station"), with the call's recorder token like
 * the rest of this prefix. The extension's content script fetches from
 * web.whatsapp.com, so these answer CORS for that origin alone — with no
 * cookies: the bearer token is the only credential.
 */
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "https://web.whatsapp.com",
  Vary: "Origin",
} as const;

function withCors(response: Response): Response {
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(CORS_HEADERS)) headers.set(name, value);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

export function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: {
      ...CORS_HEADERS,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": `Authorization, Content-Type, ${REP_RELAY_STREAM_HEADER}`,
      "Access-Control-Max-Age": "600",
    },
  });
}

/** GET — the rep's audio, their presence, hang-up and pings, as one long NDJSON stream. */
export async function GET(request: NextRequest, { params }: Params) {
  try {
    const id = (await params).id;
    return await withRecorderScope(request, id, async (row) => {
      assertRelayable(row);
      const credential = stationRelayCredential(request);
      if (!credential) throw new CallApiError(401, "Missing bearer token");
      return relayStreamResponse(request, id, "station", credential, CORS_HEADERS);
    });
  } catch (error) {
    return withCors(callApiErrorResponse(error));
  }
}

/**
 * POST — the lead's side (mono 16-bit LE PCM at REP_RELAY_SAMPLE_RATE) for
 * the rep: as an upload stream (REP_RELAY_STREAM_HEADER), read as it arrives
 * and answered when it ends, or as one chunk (the fallback). While the
 * station's down stream is open, the token it was opened with is enough,
 * without a database read per request.
 */
export async function POST(request: NextRequest, { params }: Params) {
  try {
    const id = (await params).id;
    const streaming = isRelayUploadStream(request);
    if (streaming) assertProxyRules(request);
    if (!repRelay().isAuthorized(id, "station", stationRelayCredential(request))) {
      await withRecorderScope(request, id, async (row) => assertRelayable(row));
    }
    if (streaming) await receiveRelayUpload(request, id, "station");
    else repRelay().up(id, "station", await readRelayPcm(request));
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  } catch (error) {
    return withCors(callApiErrorResponse(error));
  }
}
