import type {
  CallTimelineEntry,
  WorkerProfileCommitRequest,
  WorkerProfileCommitResponse,
  WorkerProfileUploadResponse,
  WorkerCallStatus,
  WorkerClaimRequest,
  WorkerClaimResponse,
  WorkerIncomingCallRequest,
  WorkerIncomingCallResponse,
  WorkerInboundRequest,
  WorkerInboundResponse,
  WorkerMessageClaimRequest,
  WorkerMessageClaimResponse,
  WorkerMessageResultRequest,
  WorkerLeaseRequest,
  WorkerLeaseResponse,
  WorkerReleaseRequest,
  WorkerStationStateRequest,
} from "../../../src/lib/calls/stationContract";
import { config } from "./config";

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const url = `${config().agentsdrUrl}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${config().secret}`,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    });
  } catch (err) {
    throw new Error(`${method} ${path}: could not reach ${config().agentsdrUrl} (${err instanceof Error ? err.message : String(err)})`);
  }
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const message =
      json && typeof json === "object" && "error" in json && typeof (json as { error: unknown }).error === "string"
        ? (json as { error: string }).error
        : text.slice(0, 200) || res.statusText;
    throw new Error(`${method} ${path} failed (${res.status}): ${message}`);
  }
  return json as T;
}

export function claim(body: WorkerClaimRequest): Promise<WorkerClaimResponse> {
  return request("POST", "/api/call-worker/claim", body);
}

export function leaseStations(body: WorkerLeaseRequest): Promise<WorkerLeaseResponse> {
  return request("POST", "/api/call-worker/leases", body);
}

export async function reportStationState(stationId: string, body: WorkerStationStateRequest): Promise<void> {
  await request<{ ok: true }>("POST", `/api/call-worker/stations/${encodeURIComponent(stationId)}/state`, body);
}

export async function releaseCall(callId: string, error: string): Promise<void> {
  const body: WorkerReleaseRequest = { error };
  await request<{ ok: true }>("POST", `/api/call-worker/calls/${encodeURIComponent(callId)}/release`, body);
}

export async function saveTimeline(callId: string, entries: CallTimelineEntry[]): Promise<void> {
  await request<{ ok: true }>("POST", `/api/call-worker/calls/${encodeURIComponent(callId)}/timeline`, { entries });
}

export function getCallStatus(callId: string): Promise<WorkerCallStatus> {
  return request("GET", `/api/call-worker/calls/${encodeURIComponent(callId)}`);
}

export function profileUploadUrl(stationId: string, bytes: number): Promise<WorkerProfileUploadResponse> {
  return request("POST", `/api/call-worker/stations/${encodeURIComponent(stationId)}/profile/upload-url`, { bytes });
}

export function commitProfile(stationId: string, body: WorkerProfileCommitRequest): Promise<WorkerProfileCommitResponse> {
  return request("POST", `/api/call-worker/stations/${encodeURIComponent(stationId)}/profile`, body);
}

export function claimMessage(body: WorkerMessageClaimRequest): Promise<WorkerMessageClaimResponse> {
  return request("POST", "/api/call-worker/messages/claim", body);
}

export async function reportMessageResult(messageId: string, body: WorkerMessageResultRequest): Promise<void> {
  await request<{ ok: true }>("POST", `/api/call-worker/messages/${encodeURIComponent(messageId)}/result`, body);
}

export function postInbound(stationId: string, body: WorkerInboundRequest): Promise<WorkerInboundResponse> {
  return request("POST", `/api/call-worker/stations/${encodeURIComponent(stationId)}/inbound`, body);
}

export function postIncomingCall(stationId: string, body: WorkerIncomingCallRequest): Promise<WorkerIncomingCallResponse> {
  return request("POST", `/api/call-worker/stations/${encodeURIComponent(stationId)}/incoming`, body);
}
