import "server-only";

import { createHash } from "node:crypto";
import { getSessionCookie } from "better-auth/cookies";
import { assertExactKeys, assertObject } from "@/lib/crm/categories";
import { DEMO_READ_ONLY_MESSAGE, demoRequestBlock } from "@/lib/demo/mode";
import { migrationMutationBlockReason } from "@/lib/migration/controls";
import type { CallAiLeadRequest } from "./aiCampaigns/api";
import { REP_RELAY_STREAM_HEADER, type RepRelaySide } from "./contract";
import { callSessions } from "./schema";
import { CallApiError, getCallInOrganization, isTerminalStatus } from "./sessions";
import {
  RELAY_STREAM_HEADERS,
  RelayFullError,
  REP_RELAY_MAX_CHUNK_BYTES,
  receiveUploadStream,
  repRelay,
  relayStream,
} from "./repRelay.server";

/**
 * A rep talking through a calling station (contract.ts, "a rep talking through
 * a calling station"): the call is marked in call_sessions.remote_rep, and its
 * audio goes through the in-process relay (repRelay.server.ts). These are the
 * routes' shared rules: what a body may be, which calls may be relayed, and
 * the streaming response.
 */

type CallSessionRow = typeof callSessions.$inferSelect;

/** StartCallRequest.remoteRep / CallAiLeadRequest.remoteRep: true = the rep talks; null/absent/false = not. */
export function parseRemoteRep(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value !== "boolean") throw new CallApiError(400, "remoteRep must be true or false");
  return value;
}

/**
 * POST /api/calling/ai-campaigns/:id/leads/:contactId/call — the body is
 * optional (an empty one is the AI agent's call, as before this existed).
 */
export async function readCallAiLeadRequest(request: Request): Promise<CallAiLeadRequest> {
  return parseCallAiLeadBody(await request.text());
}

export function parseCallAiLeadBody(text: string): CallAiLeadRequest {
  if (!text.trim()) return {};
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new CallApiError(400, "Request body must contain valid JSON");
  }
  assertObject(value);
  assertExactKeys(value, ["remoteRep"]);
  return { remoteRep: parseRemoteRep(value.remoteRep) };
}

// --- the relay's routes ------------------------------------------------------------

/** Whether this call's audio may go through the relay now; throws the route's error if not. */
export function assertRelayable(row: Pick<CallSessionRow, "remoteRep" | "status">): void {
  if (!row.remoteRep) throw new CallApiError(409, "This call is not one a rep talks on");
  if (isTerminalStatus(row.status)) throw new CallApiError(409, "This call is already over");
}

/** This organization's call, if a rep may talk on it now — run in the organization's scope. */
export async function requireRelayableCall(callId: string): Promise<CallSessionRow> {
  const row = await getCallInOrganization(callId);
  assertRelayable(row);
  return row;
}

/** One POST's audio: mono 16-bit PCM, whole samples, at most REP_RELAY_MAX_CHUNK_MS of it. */
export function validateRelayPcm(bytes: Uint8Array): Uint8Array {
  if (!bytes.byteLength) throw new CallApiError(400, "The body must carry audio");
  if (bytes.byteLength % 2) throw new CallApiError(400, "The body must be 16-bit PCM (an even number of bytes)");
  if (bytes.byteLength > REP_RELAY_MAX_CHUNK_BYTES) throw new CallApiError(413, `At most ${REP_RELAY_MAX_CHUNK_BYTES} bytes of audio per request`);
  return bytes;
}

/** Reads a POST's PCM body, never more than the limit allows (a lying or absent Content-Length included). */
export async function readRelayPcm(request: Request): Promise<Uint8Array> {
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > REP_RELAY_MAX_CHUNK_BYTES) {
    throw new CallApiError(413, `At most ${REP_RELAY_MAX_CHUNK_BYTES} bytes of audio per request`);
  }
  const reader = request.body?.getReader();
  if (!reader) return validateRelayPcm(new Uint8Array(0));
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > REP_RELAY_MAX_CHUNK_BYTES) {
      await reader.cancel().catch(() => {});
      throw new CallApiError(413, `At most ${REP_RELAY_MAX_CHUNK_BYTES} bytes of audio per request`);
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return validateRelayPcm(bytes);
}

/**
 * What authorized a side's stream, so its POSTs can skip the database while
 * that stream is open: a hash of the rep's session cookie, or of the
 * station's recorder token. Null: no credential at all.
 */
export function repRelayCredential(request: Request): string | null {
  const token = getSessionCookie(request);
  return token ? credentialHash(`rep:${token}`) : null;
}

export function stationRelayCredential(request: Request): string | null {
  const match = /^Bearer\s+(.+)$/.exec(request.headers.get("authorization") ?? "");
  const token = match?.[1]?.trim();
  return token ? credentialHash(`station:${token}`) : null;
}

function credentialHash(value: string): string {
  return createHash("sha256").update(value).digest("base64url");
}

/** The down stream's response for an already-authorized side. */
export function relayStreamResponse(
  request: Request,
  callId: string,
  side: RepRelaySide,
  credential: string,
  headers: Record<string, string> = {},
): Response {
  let body: ReadableStream<Uint8Array>;
  try {
    body = relayStream((subscriber) => repRelay().attach(callId, side, subscriber, credential), request.signal);
  } catch (error) {
    if (error instanceof RelayFullError) throw new CallApiError(503, error.message);
    throw error;
  }
  return new Response(body, { headers: { ...RELAY_STREAM_HEADERS, ...headers } });
}

/** A POST whose body is an upload stream (REP_RELAY_STREAM_HEADER), not one chunk. */
export function isRelayUploadStream(request: Request): boolean {
  return request.headers.get(REP_RELAY_STREAM_HEADER) === "1";
}

/**
 * An upload stream skips src/proxy.ts — its matcher leaves these out, since
 * Next.js holds back a body the proxy sees until the body has ended — so
 * what the proxy would refuse is refused here. (Its sign-in check is only a
 * cookie's presence; the routes authorize for real either way.)
 */
export function assertProxyRules(request: Request): void {
  const { pathname } = new URL(request.url);
  const blocked = migrationMutationBlockReason(pathname, request.method);
  if (blocked) throw new CallApiError(503, blocked);
  if (demoRequestBlock(pathname, request.method)) throw new CallApiError(403, DEMO_READ_ONLY_MESSAGE);
}

/**
 * Reads an already-authorized side's upload stream into the relay as it
 * arrives, until the client ends it, goes, or the relay stops it (a newer
 * stream, the call over, REP_RELAY_STREAM_MAX_MS). Then the route answers.
 */
export async function receiveRelayUpload(request: Request, callId: string, side: RepRelaySide): Promise<void> {
  if (!request.body) throw new CallApiError(400, "The body must carry audio");
  try {
    await receiveUploadStream(repRelay(), callId, side, request.body, request.signal);
  } catch (error) {
    if (error instanceof RelayFullError) throw new CallApiError(503, error.message);
    throw error;
  }
}

/** The rep hung up — run after the call was checked to be theirs. */
export function hangUpRelay(callId: string): void {
  try {
    repRelay().hangup(callId);
  } catch (error) {
    if (error instanceof RelayFullError) throw new CallApiError(503, error.message);
    throw error;
  }
}
