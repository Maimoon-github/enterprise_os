"use client";

/**
 * The rep's side of a call they talk on through a cloud calling station
 * (contract.ts, "a rep talking through a calling station"): their microphone
 * up to AgentSDR's audio relay, the lead's voice down from it, mute and
 * hang-up. No WebRTC to the station: a GoLogin station's browser rewrites and
 * strips it, and both sides reach AgentSDR anyway.
 *
 * One call at a time, held at module level rather than in a component, so it
 * survives the drawer that started it closing and client-side navigation;
 * RemoteRepCallBar (mounted once in the root layout) shows it. A full page
 * load or a closed tab ends it — the hang-up goes out as the page leaves, and
 * the relay hangs up on its own once this tab's stream has been gone a while.
 *
 *   mic → queued (`remoteRep: true`) → relay stream open at once → the station
 *   opens WhatsApp and joins the relay → dials → on call → ended
 *
 * Up: microphone → AudioWorklet → 16 kHz low-passed → RelayUplink
 * (src/lib/calls/relayUplink.ts): one long streaming POST, or POSTs of
 * ~REP_RELAY_CHUNK_MS where streaming does not get through; its steps go to
 * the console. Down: NDJSON stream → AudioBuffers at
 * 16 kHz, scheduled back to back after REP_RELAY_JITTER_MS of buffering, and
 * played through echoLoopback.ts so the echo canceller hears them.
 */

import { cancelCall, getCall, hangUpRelayedCall } from "@/lib/calls/client";
import {
  REP_RELAY_JITTER_MS,
  REP_RELAY_MAX_BUFFER_MS,
  REP_RELAY_SAMPLE_RATE,
  type CallDetail,
  type RepRelayEvent,
} from "@/lib/calls/contract";
import { base64ToBytes, createDownsampler, leBytesToFloat32, nextPlayTime } from "@/lib/calls/relayPcm";
import { RelayUplink } from "@/lib/calls/relayUplink";
import { routePlayback, type PlaybackRoute } from "./echoLoopback";
import { isRemoteRepOver, microphoneErrorText, remoteRepView, type RemoteRepStage } from "./remoteRepStage";

export type RemoteRepCallState = {
  callId: string | null;
  leadName: string;
  numberName: string | null;
  stage: RemoteRepStage;
  /** On call: when the lead picked up (epoch ms). */
  answeredAt: number | null;
  /** Ended or failed: what to tell the rep. */
  message: string | null;
  muted: boolean;
  /** On call, but the relay to the number is down for now; the call ends if it does not come back. */
  unstable: boolean;
  /** The browser held back the lead's audio until a click (autoplay rules). */
  audioBlocked: boolean;
};

/** Until the number joins: quick, so the bar keeps up. */
const POLL_WAITING_MS = 1_000;
const POLL_LIVE_MS = 2_000;
/** A rep sits waiting on this; past it, a call the number has not started is withdrawn. */
const WAIT_FOR_NUMBER_MS = 5 * 60_000;
/** After the call ends, how long to keep reading it for how it ended. */
const SETTLE_MS = 20_000;
/** The relay stream dropped: try again after this, doubling up to the cap. */
const RECONNECT_MIN_MS = 500;
const RECONNECT_MAX_MS = 4_000;
/** Microphone samples per message from the capture worklet (~10 ms at 48 kHz). */
const CAPTURE_BLOCK = 512;

type Session = {
  mic: MediaStream;
  context: AudioContext;
  capture: AudioNode;
  /** The microphone's rate down to REP_RELAY_SAMPLE_RATE, its filter state kept from block to block. */
  downsample: (block: Float32Array) => Int16Array;
  /** Root of the playback graph: every buffer from the relay plays into it. */
  playback: GainNode;
  route: PlaybackRoute | null;
  /** The microphone up to the relay; set once the call is queued. */
  uplink: RelayUplink | null;
  /** Where the next buffer from the relay starts, on the context's clock. */
  playhead: number;
  callId: string | null;
  placedAt: number;
  muted: boolean;
  /** The station's relay stream is open (its peer event). */
  stationPresent: boolean;
  /** Our relay stream is open. */
  streamUp: boolean;
  down: AbortController | null;
  reconnectMs: number;
  /** Media released: hung up, failed or over. */
  ended: boolean;
  timer: ReturnType<typeof setTimeout> | undefined;
  reconnectTimer: ReturnType<typeof setTimeout> | undefined;
};

let state: RemoteRepCallState | null = null;
let session: Session | null = null;
const listeners = new Set<() => void>();

function emit(next: RemoteRepCallState | null) {
  state = next;
  for (const listener of listeners) listener();
}

function patch(s: Session | null, update: Partial<RemoteRepCallState>) {
  // A late callback from an earlier call must not touch the current one.
  if (!state || (s && session !== s)) return;
  emit({ ...state, ...update });
}

export function subscribeRemoteRepCall(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function remoteRepCallSnapshot(): RemoteRepCallState | null {
  return state;
}

/** A call is being placed or is on (the microphone is, or is about to be, in use). */
export function isRemoteRepCallActive(): boolean {
  return !!state && !isRemoteRepOver(state.stage);
}

export type StartRemoteRepCall = {
  leadName: string;
  numberName: string | null;
  /** Queues the call on the server (e.g. callAiLead with `remoteRep: true`). */
  place: () => Promise<{ callId: string; numberName?: string | null }>;
};

/**
 * Gets the microphone and sets up the audio, then queues the call. Resolves
 * with the call id once queued, or null if it was not (the reason is in the
 * state, so the call bar shows it). Nothing is queued without a microphone.
 */
export async function startRemoteRepCall({ leadName, numberName, place }: StartRemoteRepCall): Promise<string | null> {
  if (isRemoteRepCallActive()) throw new Error("You are already on a call");
  // A finished call still on the bar: drop it, so its late reads cannot touch this one.
  if (session) clearTimeout(session.timer);
  session = null;
  emit({ callId: null, leadName, numberName, stage: "mic", answeredAt: null, message: null, muted: false, unstable: false, audioBlocked: false });

  if (typeof AudioContext === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof ReadableStream === "undefined") {
    emit({ ...state!, stage: "error", message: "This browser can't place calls — use a recent Chrome, Edge or Firefox." });
    return null;
  }
  let mic: MediaStream;
  try {
    mic = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (error) {
    emit({ ...state!, stage: "error", message: microphoneErrorText(error) });
    return null;
  }

  const context = new AudioContext();
  let s: Session | undefined;
  try {
    // Started from a click, so the context may run; a blocked one is resumed from the bar.
    await context.resume().catch(() => {});
    const capture = await startCapture(context, mic, (block) => {
      if (s) onMicBlock(s, block);
    });
    s = {
      mic,
      context,
      capture,
      downsample: createDownsampler(context.sampleRate, REP_RELAY_SAMPLE_RATE),
      playback: context.createGain(),
      route: null,
      uplink: null,
      playhead: 0,
      callId: null,
      placedAt: Date.now(),
      muted: false,
      stationPresent: false,
      streamUp: false,
      down: null,
      reconnectMs: RECONNECT_MIN_MS,
      ended: false,
      timer: undefined,
      reconnectTimer: undefined,
    };
  } catch (error) {
    for (const track of mic.getTracks()) track.stop();
    void context.close().catch(() => {});
    emit({ ...state!, stage: "error", message: error instanceof Error ? `Couldn't set up the call audio: ${error.message}` : "Couldn't set up the call audio" });
    return null;
  }
  const live = s;
  session = live;
  window.addEventListener("beforeunload", warnBeforeUnload);
  window.addEventListener("pagehide", hangUpOnUnload);

  patch(live, { stage: "placing" });
  // The loopback takes a moment to connect; let it while the call is queued.
  const routing = routePlayback(context, live.playback, { onBlocked: (blocked) => patch(live, { audioBlocked: blocked }) });
  let placed: { callId: string; numberName?: string | null };
  try {
    placed = await place();
  } catch (error) {
    void routing.then((route) => route.close());
    await finish(live, { stage: "error", message: error instanceof Error ? error.message : "Could not place the call" });
    return null;
  }
  live.callId = placed.callId;
  live.placedAt = Date.now();
  if (live.ended) {
    // Hung up while it was being queued: withdraw it.
    void routing.then((route) => route.close());
    await cancelCall(placed.callId).catch(() => {});
    return placed.callId;
  }
  patch(live, { callId: placed.callId, numberName: placed.numberName ?? numberName, stage: "waiting" });
  void openRelayStream(live);
  live.uplink = new RelayUplink({
    url: `/api/calls/${encodeURIComponent(placed.callId)}/relay`,
    log: (step) => console.info(`Call audio: ${step}`),
  });
  live.uplink.start();
  void poll(live);
  void routing.then((route) => {
    if (live.ended) route.close();
    else live.route = route;
  });
  return placed.callId;
}

export function setRemoteRepMuted(muted: boolean) {
  const s = session;
  if (!s || s.ended) return;
  s.muted = muted;
  s.uplink?.clear();
  for (const track of s.mic.getAudioTracks()) track.enabled = !muted;
  patch(s, { muted });
}

/** Retries the lead's audio after the browser blocked it; call from a click. */
export function resumeRemoteRepAudio() {
  const s = session;
  if (!s || s.ended) return;
  void s.context.resume().catch(() => {});
  void s.route?.resume().then((playing) => patch(s, { audioBlocked: !playing }));
}

/**
 * Hangs up: the relay tells the station (it ends the WhatsApp call, and the
 * recording is kept), and a call that had not connected yet is withdrawn.
 */
export async function hangUpRemoteRepCall(): Promise<void> {
  const s = session;
  if (!s || s.ended || !state) return;
  const connected = state.stage === "on-call";
  const callId = s.callId;
  if (callId) await hangUpRelayedCall(callId).catch(() => {});
  await finish(s, { stage: "ended", message: connected ? "You hung up" : "Call cancelled" }, { settle: connected });
  if (!connected && callId) await cancelCall(callId).catch(() => {});
}

/** Clears a finished call from the bar. */
export function dismissRemoteRepCall() {
  if (state && isRemoteRepOver(state.stage)) {
    if (session?.ended) clearTimeout(session.timer);
    session = null;
    emit(null);
  }
}

// --- up: the microphone -------------------------------------------------------------

/** The capture worklet: hands the microphone's first channel to the page in CAPTURE_BLOCK-sample blocks. */
const CAPTURE_WORKLET = `
class AgentsdrRelayCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.block = new Float32Array(${CAPTURE_BLOCK});
    this.length = 0;
  }
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      let offset = 0;
      while (offset < channel.length) {
        const n = Math.min(channel.length - offset, this.block.length - this.length);
        this.block.set(channel.subarray(offset, offset + n), this.length);
        this.length += n;
        offset += n;
        if (this.length === this.block.length) {
          this.port.postMessage(this.block.slice(0));
          this.length = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("agentsdr-relay-capture", AgentsdrRelayCapture);
`;

/**
 * Microphone → `onBlock` (Float32 at the context's rate), through an
 * AudioWorklet, or a ScriptProcessor where there is none. Either feeds a
 * silent gain into the destination, so the browser keeps pulling it.
 */
async function startCapture(context: AudioContext, mic: MediaStream, onBlock: (block: Float32Array) => void): Promise<AudioNode> {
  const source = context.createMediaStreamSource(mic);
  const silent = context.createGain();
  silent.gain.value = 0;
  silent.connect(context.destination);
  if (context.audioWorklet) {
    const url = URL.createObjectURL(new Blob([CAPTURE_WORKLET], { type: "application/javascript" }));
    try {
      await context.audioWorklet.addModule(url);
      const node = new AudioWorkletNode(context, "agentsdr-relay-capture", { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
      node.port.onmessage = (event: MessageEvent<Float32Array>) => onBlock(event.data);
      source.connect(node);
      node.connect(silent);
      return node;
    } catch (error) {
      console.warn("Call audio: no AudioWorklet, capturing with a ScriptProcessor", error);
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  const processor = context.createScriptProcessor(2048, 1, 1);
  processor.onaudioprocess = (event) => onBlock(new Float32Array(event.inputBuffer.getChannelData(0)));
  source.connect(processor);
  processor.connect(silent);
  return processor;
}

function onMicBlock(s: Session, block: Float32Array) {
  if (s.ended) return;
  // Always through the filter, so it keeps its history; queued only when it can go somewhere.
  const pcm = s.downsample(block);
  if (s.muted || !s.stationPresent) return;
  s.uplink?.send(pcm);
}

// --- down: the lead ----------------------------------------------------------------

/** Reads the relay stream until it ends, then reconnects while the call is on. */
async function openRelayStream(s: Session) {
  if (s.ended || !s.callId || session !== s) return;
  const abort = new AbortController();
  s.down = abort;
  let response: Response;
  try {
    response = await fetch(`/api/calls/${encodeURIComponent(s.callId)}/relay`, {
      cache: "no-store",
      headers: { Accept: "application/x-ndjson" },
      signal: abort.signal,
    });
  } catch {
    reconnect(s);
    return;
  }
  if (!response.ok || !response.body) {
    // Over, not this organization's, or signed out: the poll tells the rep how it ended.
    if ([401, 403, 404, 409].includes(response.status)) return;
    reconnect(s);
    return;
  }
  s.streamUp = true;
  s.reconnectMs = RECONNECT_MIN_MS;
  refreshUnstable(s);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let pending = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += value;
      let newline: number;
      while ((newline = pending.indexOf("\n")) >= 0) {
        const line = pending.slice(0, newline);
        pending = pending.slice(newline + 1);
        if (line.trim()) onRelayLine(s, line);
      }
    }
  } catch {
    // Dropped (network, proxy, or aborted by finish).
  }
  if (s.down === abort) s.down = null;
  s.streamUp = false;
  // Not known until the stream is back (it says so on opening).
  s.stationPresent = false;
  refreshUnstable(s);
  reconnect(s);
}

function reconnect(s: Session) {
  if (s.ended || session !== s) return;
  clearTimeout(s.reconnectTimer);
  s.reconnectTimer = setTimeout(() => void openRelayStream(s), s.reconnectMs);
  s.reconnectMs = Math.min(RECONNECT_MAX_MS, s.reconnectMs * 2);
}

function onRelayLine(s: Session, line: string) {
  let event: RepRelayEvent;
  try {
    event = JSON.parse(line) as RepRelayEvent;
  } catch {
    return;
  }
  switch (event.t) {
    case "audio":
      play(s, event.pcm);
      return;
    case "peer":
      s.stationPresent = event.present;
      if (!event.present) s.uplink?.clear();
      refreshUnstable(s);
      return;
    case "uplink":
      s.uplink?.heard();
      return;
  }
}

function play(s: Session, base64: string) {
  if (s.ended) return;
  const samples = leBytesToFloat32(base64ToBytes(base64));
  if (!samples.length) return;
  // 16 kHz buffers; the context resamples them to its own rate.
  const buffer = s.context.createBuffer(1, samples.length, REP_RELAY_SAMPLE_RATE);
  buffer.copyToChannel(samples, 0);
  const at = nextPlayTime(s.context.currentTime, s.playhead, REP_RELAY_JITTER_MS / 1000, REP_RELAY_MAX_BUFFER_MS / 1000);
  // Too far behind (a stall): drop this to catch up.
  if (at == null) return;
  const node = s.context.createBufferSource();
  node.buffer = buffer;
  node.connect(s.playback);
  node.start(at);
  s.playhead = at + buffer.duration;
}

function refreshUnstable(s: Session) {
  const unstable = state?.stage === "on-call" && (!s.streamUp || !s.stationPresent);
  if (state && state.unstable !== unstable) patch(s, { unstable });
}

// --- where the call stands -----------------------------------------------------------

async function poll(s: Session) {
  if (s.ended || !s.callId) return;
  let call: CallDetail | null = null;
  try {
    call = await getCall(s.callId);
  } catch {
    // A blip: try again below.
  }
  if (s.ended || session !== s) return;
  if (call) {
    const view = remoteRepView(call, s.stationPresent);
    if (isRemoteRepOver(view.stage)) {
      await finish(s, { stage: view.stage, message: view.message ?? null });
      return;
    }
    if ((view.stage === "waiting" || view.stage === "opening") && Date.now() - s.placedAt > WAIT_FOR_NUMBER_MS) {
      await finish(s, { stage: "error", message: "The number didn't take this call within 5 minutes — it was withdrawn. Try again." });
      await hangUpRelayedCall(s.callId).catch(() => {});
      await cancelCall(s.callId).catch(() => {});
      return;
    }
    patch(s, { stage: view.stage, answeredAt: view.answeredAt ?? state?.answeredAt ?? null });
    refreshUnstable(s);
  }
  s.timer = setTimeout(() => void poll(s), s.stationPresent ? POLL_LIVE_MS : POLL_WAITING_MS);
}

/**
 * Releases the microphone, the relay and the audio, and shows how the call
 * ended. With `settle`, keeps reading the call for a while for a better
 * ending ("Not answered", the call's length) than the hang-up can tell.
 */
async function finish(s: Session, end: { stage: "ended" | "error"; message: string | null }, { settle = false } = {}) {
  if (s.ended) return;
  s.ended = true;
  clearTimeout(s.timer);
  clearTimeout(s.reconnectTimer);
  s.down?.abort();
  s.down = null;
  s.uplink?.close();
  for (const track of s.mic.getTracks()) track.stop();
  s.capture.disconnect();
  if (s.capture instanceof AudioWorkletNode) s.capture.port.onmessage = null;
  s.route?.close();
  s.route = null;
  void s.context.close().catch(() => {});
  window.removeEventListener("beforeunload", warnBeforeUnload);
  window.removeEventListener("pagehide", hangUpOnUnload);
  patch(s, { stage: end.stage, message: end.message, unstable: false, audioBlocked: false });
  if (settle && s.callId) void settleEnding(s, s.callId, Date.now() + SETTLE_MS);
}

async function settleEnding(s: Session, callId: string, until: number) {
  if (session !== s || Date.now() > until) return;
  try {
    const view = remoteRepView(await getCall(callId), false);
    if (isRemoteRepOver(view.stage)) {
      patch(s, { stage: view.stage, message: view.message ?? state?.message ?? null });
      return;
    }
  } catch {
    // Keep the ending already shown.
  }
  s.timer = setTimeout(() => void settleEnding(s, callId, until), POLL_LIVE_MS);
}

function warnBeforeUnload(event: BeforeUnloadEvent) {
  if (!isRemoteRepCallActive()) return;
  event.preventDefault();
  // Older browsers need returnValue set to show the prompt.
  event.returnValue = "";
}

function hangUpOnUnload() {
  // Best effort, as the page goes: hang up, and withdraw a call that has not connected.
  const s = session;
  if (!s || s.ended || !s.callId) return;
  void hangUpRelayedCall(s.callId, { keepalive: true }).catch(() => {});
  if (state?.stage !== "on-call") {
    void fetch(`/api/calls/${encodeURIComponent(s.callId)}/cancel`, { method: "POST", keepalive: true }).catch(() => {});
  }
}
