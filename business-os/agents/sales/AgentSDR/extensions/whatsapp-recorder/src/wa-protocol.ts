/**
 * Messages between the two scripts the extension runs on web.whatsapp.com,
 * over window.postMessage:
 *
 *   wa-hook  (the page's own JS world) — sees WhatsApp's audio graph and
 *            microphone, and records the call.
 *   wa-agent (the extension's isolated world) — talks to the service worker:
 *            learns which call to place, clicks Voice call, ships the file.
 *
 * WhatsApp's own scripts see these messages too; they carry nothing but the
 * rep's own call.
 */

import type { StationIncomingCall, StationInboundMessage } from "../../../src/lib/calls/stationContract";

export const HOOK_SOURCE = "agentsdr-wa-hook";
export const AGENT_SOURCE = "agentsdr-wa-agent";

export type AgentToHook =
  /** Record the next call in this tab; nothing is recorded unless armed. */
  /** `agent`: the AI voice agent talks in this call — WhatsApp gets its voice as the microphone. */
  /**
   * `repRelay` (station mode, never with `agent`): the rep talks from their
   * AgentSDR tab through AgentSDR's relay — WhatsApp gets their voice (sent
   * as agent-play) as the microphone, and the lead's side comes back as
   * relay-audio from dialing on.
   */
  | {
      source: typeof AGENT_SOURCE;
      type: "arm";
      callId: string;
      agent?: boolean;
      monitor?: boolean;
      repRelay?: boolean;
    }
  | { source: typeof AGENT_SOURCE; type: "disarm" }
  /** The rep clicked the "turn on call audio" prompt — resume suspended audio. */
  | { source: typeof AGENT_SOURCE; type: "resume-audio" }
  /** Press WhatsApp's End call, wherever it is — the page or its picture-in-picture window. */
  | { source: typeof AGENT_SOURCE; type: "end-call"; callId: string }
  /** Which call, if any, wa-hook is recording or finishing off — answered with probe-result. */
  | { source: typeof AGENT_SOURCE; type: "probe" }
  /** The agent's voice (or, on a rep call, the rep's): mono 16-bit PCM at `rate` Hz, queued after what is already playing. */
  | { source: typeof AGENT_SOURCE; type: "agent-play"; callId: string; pcm: ArrayBuffer; rate: number }
  /** The lead talked over the agent: drop the agent's voice still queued. */
  | { source: typeof AGENT_SOURCE; type: "agent-interrupt"; callId: string }
  /** The agent ended the call: hang up once its goodbye has finished playing. */
  | { source: typeof AGENT_SOURCE; type: "agent-hangup"; callId: string }
  /** Press WhatsApp's Accept on the incoming call (station mode; armed first) — answered with accept-result. */
  | { source: typeof AGENT_SOURCE; type: "accept-call"; callId: string };

export type HookToAgent =
  /** WhatsApp opened the microphone for the call: it is dialing or ringing. */
  | { source: typeof HOOK_SOURCE; type: "dialing"; callId: string }
  /** The call timer appeared — the lead picked up — and recording began. */
  | { source: typeof HOOK_SOURCE; type: "answered"; callId: string; answeredAt: number; timerSeen: boolean }
  | { source: typeof HOOK_SOURCE; type: "audio-suspended"; callId: string }
  /**
   * The finished recording. It runs from `startedAt` (the call opening the
   * microphone) to `endedAt`; the lead picked up at `answeredAt`, in between.
   */
  | {
      source: typeof HOOK_SOURCE;
      type: "recording";
      callId: string;
      blob: Blob;
      startedAt: number;
      answeredAt: number;
      endedAt: number;
    }
  /** The call ended without the timer ever appearing. */
  | { source: typeof HOOK_SOURCE; type: "not-answered"; callId: string; dialedAt: number; endedAt: number }
  | { source: typeof HOOK_SOURCE; type: "recording-failed"; callId: string; error: string }
  | { source: typeof HOOK_SOURCE; type: "end-result"; callId: string; clicked: boolean }
  /** WhatsApp's own call screen changed what it says ("Calling…", "Ringing…"). */
  | { source: typeof HOOK_SOURCE; type: "call-status"; callId: string; text: string }
  /** What wa-hook can see of the call UI, when that changes — for the timing table. */
  | { source: typeof HOOK_SOURCE; type: "diag"; callId: string; text: string }
  | { source: typeof HOOK_SOURCE; type: "probe-result"; callId: string | null }
  /** WhatsApp's call screen appeared for this call — the rep can go back to AgentSDR. */
  | { source: typeof HOOK_SOURCE; type: "call-ui"; callId: string }
  /** The lead's side of an agent call, from the pick-up on: mono 16-bit PCM at 16 kHz. */
  | { source: typeof HOOK_SOURCE; type: "agent-audio"; callId: string; pcm: ArrayBuffer }
  /** The lead's side of a rep call (armed with repRelay), from dialing on: mono 16-bit PCM at REP_RELAY_SAMPLE_RATE. */
  | { source: typeof HOOK_SOURCE; type: "relay-audio"; callId: string; pcm: ArrayBuffer }
  /** Whether Accept was pressed on the incoming call; `labels`: the call's buttons seen (digits masked), for diagnosis. */
  | { source: typeof HOOK_SOURCE; type: "accept-result"; callId: string; clicked: boolean; labels: string };

// --- station messaging --------------------------------------------------------
// A calling station's WhatsApp messaging (station mode only): wa-hook reads
// messages from WhatsApp's own message store once wa-agent enables it. Its
// own `source` values, so the call path's listeners never see these.

export const HOOK_MESSAGING_SOURCE = "agentsdr-wa-hook-messaging";
export const AGENT_MESSAGING_SOURCE = "agentsdr-wa-agent-messaging";

export type AgentToHookMessaging =
  /** Start reading WhatsApp's message store — only on a calling station, never a rep's own WhatsApp. */
  | { source: typeof AGENT_MESSAGING_SOURCE; type: "messaging-enable" }
  /** Answered with messaging-source. */
  | { source: typeof AGENT_MESSAGING_SOURCE; type: "messaging-status" }
  /**
   * The newest message sent from this number to `chatDigits` with this body,
   * since `sinceMs` — or, given `keyId`, that message. Answered with found-sent.
   */
  | {
      source: typeof AGENT_MESSAGING_SOURCE;
      type: "find-sent";
      requestId: string;
      chatDigits: string;
      body: string;
      sinceMs: number;
      keyId: string | null;
    };

export type HookToAgentMessaging =
  /** "store": the message-store listener is attached; "none": not (yet). */
  | { source: typeof HOOK_MESSAGING_SOURCE; type: "messaging-source"; capability: "store" | "none" }
  /** Messages WhatsApp added to its store (new ones, either direction). */
  | { source: typeof HOOK_MESSAGING_SOURCE; type: "messages"; messages: StationInboundMessage[] }
  | { source: typeof HOOK_MESSAGING_SOURCE; type: "found-sent"; requestId: string; providerMessageId: string | null }
  /** A step worth the station's log. */
  | { source: typeof HOOK_MESSAGING_SOURCE; type: "messaging-log"; text: string }
  /** A WhatsApp call started ringing on this number (from the call store, or the page's incoming-call screen). */
  | { source: typeof HOOK_MESSAGING_SOURCE; type: "incoming-call"; call: StationIncomingCall }
  /** WhatsApp removed that call: it was answered, declined or missed. */
  | { source: typeof HOOK_MESSAGING_SOURCE; type: "incoming-call-ended"; waCallId: string };
