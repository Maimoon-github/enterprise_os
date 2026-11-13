import type { BrowserContext, Worker } from "playwright-core";
import type { RecorderCallRequest } from "../../../src/lib/calls/contract";
import type { StationIncomingCall, StationInboundTake, StationSendResult, WorkerCall } from "../../../src/lib/calls/stationContract";

/**
 * Station mode for calls. Messaging needs 0.21.0+ and answering incoming
 * calls 0.22.0+, each detected by its functions (supportsMessaging,
 * supportsIncoming); a rep talking through the station needs 0.24.0+, by
 * version (supportsRepCalls), since it adds no function of its own (0.23.x
 * linked the rep by WebRTC, which a GoLogin browser rewrites and strips, and
 * expects a WebRTC offer where 0.24.0 takes `remoteRep: true` and AgentSDR's
 * audio relay).
 */
export const MIN_EXTENSION_VERSION = "0.17.0";
export const REP_CALL_MIN_VERSION = "0.24.0";

export type StationCallRequest = Omit<RecorderCallRequest, "source" | "type" | "requestId">;
export type StationResult = { ok: true } | { ok: false; error: string };
export type ActiveCall = { callId: string; dialedAt: number | null; answeredAt: number | null } | null;

export type StationWorker = {
  version: string;
  startCall(req: StationCallRequest): Promise<StationResult>;
  endCall(callId: string): Promise<unknown>;
  activeCall(): Promise<ActiveCall>;
  /** The extension's call log since the last drain (empty on extensions before 0.17.4). */
  drainLog(): Promise<string[]>;
  /** The extension has sendMessage and takeInbound (0.21.0+); without them both throw. */
  supportsMessaging: boolean;
  /** Sends a WhatsApp message from the number (0.21.0+). */
  sendMessage(req: { phone: string; text: string }): Promise<StationSendResult>;
  /** Takes (and clears) the messages the extension saw since the last take (0.21.0+). */
  takeInbound(): Promise<StationInboundTake>;
  /** The extension has takeIncomingCalls and answerCall (0.22.0+); without them both throw. */
  supportsIncoming: boolean;
  /** Takes the calls ringing on the number since the last take, young enough to answer (0.22.0+). */
  takeIncomingCalls(): Promise<StationIncomingCall[]>;
  /** Answers the ringing call `waCallId` as AgentSDR's call `callId` (0.22.0+). */
  answerCall(req: StationCallRequest & { waCallId: string }): Promise<StationResult>;
  /** The extension can place a call the rep talks on from AgentSDR (`remoteRep`, 0.24.0+). */
  supportsRepCalls: boolean;
};

/**
 * What startCall / answerCall are given for a claimed call: the AI agent, or
 * — for a rep call — `remoteRep: true` and no agent (the extension then
 * carries the audio through AgentSDR's relay, with the call's own token).
 */
export function stationCallRequest(call: WorkerCall, apiBase: string, clickedAt: number): StationCallRequest {
  return {
    callId: call.id,
    phone: call.phone,
    recorderToken: call.recorderToken,
    apiBase,
    lead: call.lead,
    ...(call.remoteRep
      ? { agent: null, remoteRep: true }
      : { agent: { brief: call.brief, name: call.agentName, voice: call.agentVoice } }),
    clickedAt,
  };
}

function versionAtLeast(version: string, min: string): boolean {
  const a = version.split(".").map((n) => parseInt(n, 10) || 0);
  const b = min.split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d !== 0) return d > 0;
  }
  return true;
}

const isRecorderWorker = (w: Worker) => w.url().startsWith("chrome-extension://") && w.url().endsWith("/background.js");

type Probe = { version: string | null; api: boolean; messaging: boolean; incoming: boolean };

/** The extension's station version in this worker, and whether its chrome.* calls work. */
async function probe(worker: Worker): Promise<Probe> {
  return worker
    .evaluate(async () => {
      const scope = globalThis as unknown as {
        agentsdrStation?: { version: string; sendMessage?: unknown; takeInbound?: unknown; takeIncomingCalls?: unknown; answerCall?: unknown };
        chrome: { storage: { session: { get(keys: null): Promise<unknown> } } };
      };
      const station = scope.agentsdrStation;
      const version = station?.version ?? null;
      const messaging = typeof station?.sendMessage === "function" && typeof station?.takeInbound === "function";
      const incoming = typeof station?.takeIncomingCalls === "function" && typeof station?.answerCall === "function";
      try {
        await scope.chrome.storage.session.get(null);
        return { version, api: true, messaging, incoming };
      } catch {
        return { version, api: false, messaging, incoming };
      }
    })
    .catch(() => ({ version: null, api: false, messaging: false, incoming: false }));
}

/**
 * The recorder's background worker that is actually running. Reopening a
 * GoLogin profile lists two of them (23 Oct 2026): a stale one carried over
 * from the last session, which still evaluates — even reports its version —
 * but whose every chrome.* call fails "No SW", and the live one. Taking the
 * first found failed every call on a relinked number, so each candidate is
 * tested with a real API call, newest first.
 */
async function liveWorker(
  context: BrowserContext,
  timeoutMs: number,
): Promise<{ worker: Worker; version: string; messaging: boolean; incoming: boolean } | null> {
  const deadline = Date.now() + timeoutMs;
  do {
    for (const worker of context.serviceWorkers().filter(isRecorderWorker).reverse()) {
      const { version, api, messaging, incoming } = await probe(worker);
      if (version && api) return { worker, version, messaging, incoming };
    }
    await new Promise((r) => setTimeout(r, 500));
  } while (Date.now() < deadline);
  return null;
}

export async function stationWorker(context: BrowserContext): Promise<StationWorker> {
  if (!context.serviceWorkers().some(isRecorderWorker)) {
    await context.waitForEvent("serviceworker", { predicate: isRecorderWorker, timeout: 30_000 }).catch(() => {
      throw new Error("The recorder extension's service worker did not start — is the extension installed in this browser profile?");
    });
  }
  // The station object is set when the worker script finishes evaluating; allow a moment.
  const found = await liveWorker(context, 10_000);
  if (!found) throw new Error("The recorder extension has no working station mode (agentsdrStation missing, or its worker is not running) — update the extension");
  const { version } = found;
  let current = found.worker;
  if (!versionAtLeast(version, MIN_EXTENSION_VERSION)) {
    throw new Error(`The recorder extension is ${version}; station mode needs ${MIN_EXTENSION_VERSION} or newer`);
  }
  let drainFailed = false;
  /** Chrome stops and restarts an extension's worker as it likes; a stale handle is swapped for the live one. */
  const live = async (): Promise<Worker> => {
    if ((await probe(current)).api) return current;
    current = (await liveWorker(context, 5_000))?.worker ?? current;
    return current;
  };

  type Station = {
    startCall(r: unknown): Promise<unknown>;
    endCall(id: string): Promise<unknown>;
    activeCall(): Promise<unknown>;
    drainLog?(): string[] | Promise<string[]>;
    sendMessage(r: { phone: string; text: string }): Promise<unknown>;
    takeInbound(): Promise<unknown>;
    takeIncomingCalls(): Promise<unknown>;
    answerCall(r: unknown): Promise<unknown>;
  };
  return {
    version,
    startCall: async (req) => (await live()).evaluate((r) => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.startCall(r), req) as Promise<StationResult>,
    endCall: async (callId) => (await live()).evaluate((id) => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.endCall(id), callId),
    activeCall: async () => (await live()).evaluate(() => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.activeCall()) as Promise<ActiveCall>,
    drainLog: async () => {
      try {
        return await (await live()).evaluate(() => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.drainLog?.() ?? []);
      } catch (error) {
        if (!drainFailed) console.warn(`[worker] could not read the extension's call log: ${error instanceof Error ? error.message.split("\n")[0] : String(error)}`);
        drainFailed = true;
        return [];
      }
    },
    supportsMessaging: found.messaging,
    sendMessage: async (req) => {
      if (!found.messaging) throw new Error(`The recorder extension ${version} cannot send messages (needs 0.21.0+)`);
      return (await live()).evaluate((r) => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.sendMessage(r), req) as Promise<StationSendResult>;
    },
    takeInbound: async () => {
      if (!found.messaging) throw new Error(`The recorder extension ${version} cannot read messages (needs 0.21.0+)`);
      return (await live()).evaluate(() => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.takeInbound()) as Promise<StationInboundTake>;
    },
    supportsIncoming: found.incoming,
    takeIncomingCalls: async () => {
      if (!found.incoming) throw new Error(`The recorder extension ${version} cannot answer calls (needs 0.22.0+)`);
      return (await live()).evaluate(() => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.takeIncomingCalls()) as Promise<
        StationIncomingCall[]
      >;
    },
    answerCall: async (req) => {
      if (!found.incoming) throw new Error(`The recorder extension ${version} cannot answer calls (needs 0.22.0+)`);
      return (await live()).evaluate((r) => (globalThis as unknown as { agentsdrStation: Station }).agentsdrStation.answerCall(r), req) as Promise<StationResult>;
    },
    supportsRepCalls: versionAtLeast(version, REP_CALL_MIN_VERSION),
  };
}
