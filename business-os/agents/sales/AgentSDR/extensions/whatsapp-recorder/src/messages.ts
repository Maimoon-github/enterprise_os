/**
 * Messages between the extension's own contexts: the service worker,
 * wa-agent on web.whatsapp.com, and the bridge content script on the app's
 * pages.
 *
 * All of them listen on chrome.runtime.onMessage, which every extension
 * context receives, so each message names its `target` and receivers ignore
 * the rest.
 */

import type {
  AgentOutcomeKind,
  AgentTokenResponse,
  RecorderAgent,
  RecorderBridgeRequest,
  RecorderCallPhase,
  RecorderLead,
} from "../../../src/lib/calls/contract";
import type {
  StationIncomingCall,
  StationInboundMessage,
  StationInboundSource,
  StationSendResult,
} from "../../../src/lib/calls/stationContract";

/** A call placed from the app, which the next recording belongs to. */
export type ActiveCall = {
  callId: string;
  recorderToken: string;
  apiBase: string;
  /** E.164. */
  phone: string;
  requestedAt: number;
  /** The WhatsApp Web tab the chat was opened in. */
  tabId?: number;
  /** When wa-agent clicked Voice call; set means the call is handled there. */
  dialedAt?: number;
  /** When the lead picked up (the call timer appeared). */
  answeredAt?: number;
  lead?: RecorderLead | null;
  /** The AgentSDR tab the call was placed from — "Back to AgentSDR" returns there. */
  appTabId?: number;
  /** Set: the AI voice agent talks in this call instead of the rep. */
  agent?: RecorderAgent | null;
  /** Station mode only: the rep talks from their AgentSDR tab, through AgentSDR's audio relay — see rep-relay.ts. */
  remoteRep?: boolean;
  /**
   * Started by AgentSDR's call worker in a cloud browser (station mode), not
   * by a rep: there is no AgentSDR tab to return to or report phases to, so
   * phases go to the server instead.
   */
  station?: boolean;
  /**
   * An incoming call the station answers (station mode only). Never dialed:
   * `dialedAt` is set when it is answered, so a reloaded tab never calls out.
   */
  inbound?: boolean;
};

/** What the service worker keeps after a call ends, for the call card's status checks. */
export type RecentCall = Pick<ActiveCall, "callId" | "recorderToken" | "apiBase" | "appTabId" | "station"> & { endedAt: number };

/**
 * What wa-agent is told about the call to place in its tab — never the token,
 * except on a rep call. `station`: a cloud calling station's call — no rep at
 * this machine.
 */
export type WaCall = {
  callId: string;
  phone: string;
  lead: RecorderLead | null;
  agent: boolean;
  station: boolean;
  /**
   * Set on a rep call (station mode): where wa-agent reaches AgentSDR's audio
   * relay, and the call's recorder token, which is what authorizes it. The
   * relay is a stream of the rep's voice that must reach the page's audio
   * graph with no extra hop, so wa-agent calls it itself; wa-agent is the
   * extension's isolated world, not the page — WhatsApp's own scripts never
   * see the token.
   */
  repRelay: RepRelayAccess | null;
};

export type RepRelayAccess = { apiBase: string; recorderToken: string };

/** The service worker's answer to wa:agent-token. */
export type AgentTokenResult = ({ ok: true } & AgentTokenResponse) | { ok: false; error: string };

/**
 * Service worker → wa-agent in an already-loaded WhatsApp tab: open this chat
 * in place (with `text` typed in, for a follow-up), then place `call` if one
 * is given. Answered with a BridgeResult; not ok means "reload instead".
 */
export type AgentCommand =
  | {
      target: "wa-agent";
      type: "open";
      /** Digits only, country code first. */
      phone: string;
      text: string | null;
      call: WaCall | null;
    }
  /** Hang up `callId` — answered with a BridgeResult saying whether End call was pressed. */
  | { target: "wa-agent"; type: "end"; callId: string }
  /** Which calls this tab is still busy with — answered with a ProbeResult. */
  | { target: "wa-agent"; type: "probe" }
  // Station messaging (see "station messaging" in wa-agent.ts):
  /** Start reading this number's messages (wa-hook's store listener). Answered with a BridgeResult. */
  | { target: "wa-agent"; type: "messaging-enable" }
  /**
   * Send `text` to `phone` (digits) from this number. `afterReload`: the tab
   * was just loaded at /send?phone=… for it. Answered with a WaSendOutcome.
   */
  | { target: "wa-agent"; type: "send-message"; phone: string; text: string; afterReload: boolean }
  /** Read unread chats from the chat list (the DOM fallback). Answered with a WaScanResult. */
  | { target: "wa-agent"; type: "scan-inbound" }
  /**
   * Answer the call ringing in this tab as `call` (station mode): arm, start
   * the agent, press Accept. Answered with a BridgeResult once armed; the
   * call's outcome is reported like a placed call's.
   */
  | { target: "wa-agent"; type: "answer"; call: WaCall };

/**
 * wa-agent's answer to send-message: the station's result, or `reload` — the
 * chat could not be opened in place and nothing was typed; the service worker
 * may load the tab at /send?phone=… and ask again.
 */
export type WaSendOutcome = StationSendResult | { ok: false; reload: true; error: string };

/** wa-agent's answer to scan-inbound. `skipped`: a call is on, nothing was opened. */
export type WaScanResult = { ok: true; messages: StationInboundMessage[] } | { ok: false; skipped: boolean; error: string };

/** A call is busy while it is being recorded, finished off, or uploaded. */
export type ProbeResult = { busyCallIds: string[] };

/** Service worker → the bridge in the AgentSDR tab that placed a call. */
export type BridgeCommand =
  | { target: "bridge"; type: "call:update"; callId: string; phase: RecorderCallPhase }
  /** Printed to the AgentSDR tab's console: how long each step of a call took. */
  | { target: "bridge"; type: "call:timing"; callId: string; steps: { step: string; ms: number }[] };

export type BackgroundMessage =
  | { target: "background"; type: "bridge"; request: RecorderBridgeRequest }
  // From wa-agent on web.whatsapp.com, about the call in its own tab:
  | { target: "background"; type: "wa:hello" }
  /** `pressed`: the extension pressed Voice call itself (false: the rep has to). */
  | { target: "background"; type: "wa:dialed"; callId: string; pressed: boolean }
  /** `noCallButton`: the chat opened but has no Voice call button (a business number). */
  | { target: "background"; type: "wa:not-on-whatsapp"; callId: string; noCallButton?: boolean }
  | { target: "background"; type: "wa:answered"; callId: string; answeredAt: number }
  | { target: "background"; type: "wa:not-answered"; callId: string; dialedAt: number; endedAt: number }
  | { target: "background"; type: "wa:recording-failed"; callId: string; error: string }
  /** The call card polls the transcript's progress; answered with RecorderCallStatus | null. */
  | { target: "background"; type: "wa:status"; callId: string }
  /**
   * Back to the AgentSDR tab the call came from. `auto`: sent by the extension
   * itself at the end of a call, not by the rep — skipped when the rep was
   * already switched back when the call rang.
   */
  | { target: "background"; type: "wa:focus-app"; callId: string; auto?: boolean }
  /** WhatsApp's call screen is up: the moment to switch the rep back to AgentSDR. */
  | { target: "background"; type: "wa:call-shown"; callId: string }
  /** The call card's phase changed; forwarded to the AgentSDR tab that placed the call. */
  | { target: "background"; type: "wa:phase"; callId: string; phase: RecorderCallPhase }
  /** A timed step of a call, for the timing table printed in the AgentSDR tab's console. */
  | { target: "background"; type: "wa:trace"; callId: string; step: string }
  /** A Gemini Live token for the AI agent on this call; answered with an AgentTokenResult. */
  | { target: "background"; type: "wa:agent-token"; callId: string }
  /** The AI agent called record_outcome; answered with a BridgeResult. */
  | { target: "background"; type: "wa:agent-outcome"; callId: string; outcome: AgentOutcomeReport }
  // Station messaging, from wa-agent:
  /** On load: should this tab read its messages? Answered with { enabled: boolean }. */
  | { target: "background"; type: "wa:messaging-hello" }
  /** Whether wa-hook's message-store listener is attached. */
  | { target: "background"; type: "wa:messaging-source"; capability: Exclude<StationInboundSource, "dom"> }
  /** Messages read from the store, for the call worker's next take. */
  | { target: "background"; type: "wa:inbound"; messages: StationInboundMessage[] }
  /** A messaging step for the station's log (drainLog). */
  | { target: "background"; type: "wa:msg-log"; step: string }
  /** A WhatsApp call is ringing on this number (station mode), for the call worker's next takeIncomingCalls. */
  | { target: "background"; type: "wa:incoming-call"; call: StationIncomingCall }
  /** That ring stopped (WhatsApp removed the call). */
  | { target: "background"; type: "wa:incoming-ended"; waCallId: string };

/** What the AI agent reports through record_outcome (the body of POST .../outcome). */
export type AgentOutcomeReport = { outcome: AgentOutcomeKind; summary: string | null; when: string | null; whenAt?: string | null };

/** The heard-audio test option: wa-agent streams the WAV of what the AI agent heard to the service worker. */
export const WA_HEARD_AUDIO_PORT = "wa-heard-audio";
export type WaHeardAudioPortMessage =
  | { type: "meta"; callId: string }
  /** base64 — runtime messaging is JSON-only. */
  | { type: "chunk"; data: string }
  | { type: "end" };

/** The "wa-recording" port: wa-agent streams the file to the service worker. */
export const WA_RECORDING_PORT = "wa-recording";
export type WaRecordingPortMessage =
  /** The recording runs startedAt → endedAt; the lead picked up at answeredAt. */
  | { type: "meta"; callId: string; mimeType: string; startedAt: number; answeredAt: number; endedAt: number }
  /** base64 — runtime messaging is JSON-only, so a Blob cannot cross it. */
  | { type: "chunk"; data: string }
  | { type: "end" };

/** The service worker's answer to a bridged request. */
export type BridgeResult = { ok: true } | { ok: false; error: string };
