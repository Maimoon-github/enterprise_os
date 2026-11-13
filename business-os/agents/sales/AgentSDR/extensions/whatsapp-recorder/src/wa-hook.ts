/**
 * Records a WhatsApp Web call from inside the page. Runs in the page's own JS
 * world at document_start, before WhatsApp's code loads.
 *
 * What the probe established (29 Sep 2026): WhatsApp Web does not carry call
 * audio as WebRTC media tracks. Its own engine plays the other side through an
 * AudioWorklet connected to an AudioContext's destination, and reads the
 * microphone with getUserMedia — acquired when the call starts, stopped when
 * it ends, whoever hangs up. So the recording is assembled from exactly
 * those two points:
 *   - the other side: every node WhatsApp connects to a speaker destination
 *     is also connected into our recording graph (AudioNode.connect patch);
 *   - the rep: a clone of the call's microphone track.
 * Our graph lives in WhatsApp's own, already-running AudioContext, so
 * Chrome's autoplay policy never silences the recording.
 *
 * When: the recorder starts as soon as the call opens the microphone —
 * before the pick-up, so the lead's first words are never lost to the time it
 * takes to notice it. The pick-up is when the call timer appears; the timer
 * counts from it, so its reading dates the pick-up precisely even when it is
 * noticed a moment late. The recording stops when the timer disappears, End
 * call goes, or the microphone is released; a call never picked up is
 * discarded.
 *
 * Where: while its tab is in the background, WhatsApp moves the call UI into
 * a Document Picture-in-Picture window (seen 29 Sep 2026). So End call and
 * the timer are looked for in the page and that window, and a missing End
 * call must stay missing a few checks running — the hand-over between the
 * two must not read as a hang-up. A timer is a m:ss text near End call that changes — a voice
 * note's static "0:12" never ticks. If no timer shows within a minute of the
 * mic opening, recording starts anyway, in case WhatsApp's markup changed.
 *
 * Nothing is recorded unless wa-agent armed this tab for a call placed from
 * AgentSDR — the rep's own calls are never touched.
 *
 * An agent call (trial) is armed with `agent`: the AI voice agent talks
 * instead of the rep. WhatsApp's getUserMedia then gets a microphone track
 * that carries the agent's voice (a MediaStreamAudioDestinationNode) in place
 * of the real one, which is released at once; the lead's side, from the
 * pick-up on, goes to wa-agent as 16 kHz PCM for the model (live-agent.ts).
 * The rep hears both sides through the speakers, and the recording keeps the
 * agent left and the lead right, as it would the rep.
 *
 * A rep call (station mode) is armed with `repRelay`: the rep talks from
 * their own AgentSDR tab, through this cloud browser, and AgentSDR relays the
 * audio (wa-agent holds the relay — rep-relay.ts). It is an agent call with
 * the rep in the agent's place: their voice arrives as agent-play and becomes
 * WhatsApp's microphone, played with a jitter buffer (REP_RELAY_JITTER_MS,
 * dropped past REP_RELAY_MAX_BUFFER_MS so it catches up rather than lags);
 * the lead's side goes back as relay-audio from the moment WhatsApp dials, so
 * the rep hears it ring. No WebRTC of ours: a GoLogin browser rewrites and
 * strips it (29 Oct 2026). The recording keeps the rep left and the lead right.
 */

import { createDownsampler } from "./downsample";
import {
  REP_RELAY_JITTER_MS,
  REP_RELAY_MAX_BUFFER_MS,
  REP_RELAY_SAMPLE_RATE,
} from "../../../src/lib/calls/contract";
import { INCOMING_CALL_MAX_AGE_MS, type StationInboundMessage } from "../../../src/lib/calls/stationContract";
import { isAcceptLabel, maskDigits, phoneFromScreenText } from "./incoming";
import { isNonPersonalJid, jidToPhone, parseMessageId, serializedMessageId, storeMessage } from "./inbound";
import {
  AGENT_MESSAGING_SOURCE,
  AGENT_SOURCE,
  HOOK_MESSAGING_SOURCE,
  HOOK_SOURCE,
  type AgentToHook,
  type AgentToHookMessaging,
  type HookToAgent,
  type HookToAgentMessaging,
} from "./wa-protocol";

/**
 * A getUserMedia track stopped sooner than this was a permission check, not a
 * call. WhatsApp stops its check within the same millisecond (probe, 29 Sep
 * 2026), so this only needs to outlast that.
 */
const MIC_SETTLE_MS = 300;
/**
 * How often the call UI is read. 0.2 s was tried for a faster pick-up
 * (23 Oct 2026) and cloud calls then crashed while ringing or were taken for
 * hung up at the pick-up — the moments WhatsApp builds or moves its
 * picture-in-picture call window, which this reads. Back to 0.5 s.
 */
const WATCH_INTERVAL_MS = 500;
const NO_TIMER_FALLBACK_MS = 60_000;
/**
 * How many checks running the timer, or End call, must be missing before the
 * call counts as over. Background tabs throttle intervals to 1 s, so this is
 * a few seconds — enough to ride out the move into picture-in-picture.
 */
const TIMER_GONE_CHECKS = 4;
const END_BUTTON_GONE_CHECKS = 4;
/** Armed this long with no call UI ever showing: the call was never placed. */
const ARMED_WITHOUT_CALL_MS = 90_000;
const TIMER_PATTERN = /^\d{1,2}:\d{2}(?::\d{2})?$/;
/** How far above End call to look for the timer before the search gets too wide. */
const MAX_TIMER_SEARCH_ELEMENTS = 400;
/** WhatsApp's hang-up control, by its label in the page or its picture-in-picture window. */
const END_CALL_LABEL = /end call|hang ?up|leave call/i;
const END_CALL_ICON = /call-end|end-call|hang-?up/i;
const STATUS_PATTERN = /^(calling|ringing|connecting|reconnecting)/i;
const STILL_RINGING = /^(calling|ringing)/i;
/**
 * A timer this young next to End call on the page is a call just picked up,
 * not a voice note's length — so it counts on first sight, without waiting to
 * see it tick. In the picture-in-picture window, which holds only the call,
 * any timer counts on first sight.
 */
const FRESH_TIMER_SECONDS = 10;

type Connect = (this: AudioNode, destination: AudioNode | AudioParam, output?: number, input?: number) => unknown;
type Disconnect = (this: AudioNode, destination: AudioNode) => void;

type Recording = { recorder: MediaRecorder; chunks: Blob[]; startedAt: number };

/** The audio graph of an agent call (or a rep call): the agent's voice in, the lead's side out. */
type AgentRig = {
  callId: string;
  /** A rep call through AgentSDR's relay: the "agent's voice" is the rep's, and the lead's side goes out from dialing on. */
  relay: boolean;
  context: AudioContext;
  /** The agent's voice, fanned out to the call's microphone tracks and the rep's speakers. */
  voice: GainNode;
  /** The agent's voice scheduled to play, stopped when the lead talks over it. */
  queued: Set<AudioBufferSourceNode>;
  /** Context time the queued voice runs to. */
  playHead: number;
  /** Set at the pick-up: from then on the lead's side goes to the model (a rep call's goes from the start). */
  listening: boolean;
  hangupTimer: number;
  /**
   * The real microphone, held (muted) for the call: a page that is capturing
   * may play audio without a click (Chrome's autoplay policy), which keeps the
   * agent's context running.
   */
  held: MediaStreamTrack[];
  /** Counters for the diagnostics, reported once each. */
  sentAudio: boolean;
  playedAudio: boolean;
  /** A rep call: times queued audio was dropped to catch up, for the log. */
  catchUps: number;
};

/** The sample rate Gemini Live takes its input at. */
const AGENT_INPUT_RATE = 16_000;
/** ScriptProcessor block size: ~85 ms at 48 kHz, within the 20–100 ms chunks Live wants. */
const AGENT_CAPTURE_FRAMES = 4096;
/** A rep call's: ~43 ms at 48 kHz, about one relay chunk (REP_RELAY_CHUNK_MS) — less delay to the rep. */
const RELAY_CAPTURE_FRAMES = 2048;
/** Small lead so the first chunk of a reply does not start mid-render. */
const AGENT_PLAY_LEAD_S = 0.03;
/** After the agent's goodbye has played, this long before End call is pressed. */
const AGENT_HANGUP_GRACE_MS = 800;

type Session = {
  callId: string;
  /** WhatsApp's own microphone track for the call. */
  micTrack: MediaStreamTrack;
  micClone: MediaStreamTrack;
  /** The context our recording graph lives in. */
  context: AudioContext;
  remoteBus: GainNode;
  output: MediaStreamAudioDestinationNode;
  /** Connections we added, undone when the call ends. */
  links: [AudioNode, AudioNode][];
  /** Other contexts' playback, bridged into `context` through a MediaStream. */
  bridges: Map<BaseAudioContext, MediaStreamAudioDestinationNode>;
  dialedAt: number;
  /** When the lead picked up; null while the call is still ringing. */
  answeredAt: number | null;
  lastTimerText: string | null;
  timerSeen: boolean;
  /** Checks running the (trusted) timer has not moved — a frozen timer means the call ended. */
  timerStill: number;
  sawEndButton: boolean;
  endButtonMissing: number;
  /** WhatsApp's last "Calling…" / "Ringing…" text, reported when it changes. */
  lastStatusText: string | null;
  /** Where the call UI was last seen, reported when it changes. */
  lastWhere: string | null;
  /** Running from the moment the call opened the microphone. */
  recording: Recording;
  watch: number;
};

const scope = window as unknown as { __agentsdrHook?: boolean };
if (!scope.__agentsdrHook) {
  scope.__agentsdrHook = true;
  install();
}

/** Sample rates the page asked AudioContexts for, while fixIgnoredSampleRates is in force. */
const ignoredRateRequests = new Set<number>();

/**
 * CloakBrowser's free build (Chromium 145) answers `new AudioContext({
 * sampleRate: 16000 })` with a context that reports 48000 Hz yet renders
 * about a quarter of real time; audio carried from it to another context
 * comes out garbled (measured 23 Oct 2026: 0.5 dB SNR, against 58 dB in
 * plain Chromium). Cloud calls in it were choppy to the lead, and the agent
 * heard loud noise instead of the lead's voice. Where a requested rate is not
 * honoured, every AudioContext is made at the default rate instead — which
 * that browser handles correctly — and the page reads the real rate from it.
 */
function fixIgnoredSampleRates(): boolean {
  const Native = window.AudioContext;
  if (!Native) return false;
  try {
    const probe = new Native({ sampleRate: 16000 });
    const honoured = probe.sampleRate === 16000;
    void probe.close();
    if (honoured) return false;
  } catch {
    return false;
  }
  class DefaultRateAudioContext extends Native {
    constructor(options?: AudioContextOptions) {
      const { sampleRate, ...rest } = options ?? {};
      if (sampleRate) ignoredRateRequests.add(sampleRate);
      super(rest);
    }
  }
  window.AudioContext = DefaultRateAudioContext;
  (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext = DefaultRateAudioContext;
  return true;
}

/**
 * WhatsApp Web's peer connections, so an agent call can log how its audio
 * travels (direct or through a relay, UDP or TCP, round-trip time). On the
 * call worker "Connecting…" took 4.5 s against 0.5 s on a Mac (23 Oct 2026);
 * this says why. Watching only — the connections are not changed.
 */
const peers = new Set<WeakRef<RTCPeerConnection>>();
function trackPeerConnections(): void {
  const Native = window.RTCPeerConnection;
  if (!Native) return;
  class TrackedPeerConnection extends Native {
    constructor(configuration?: RTCConfiguration) {
      super(configuration);
      peers.add(new WeakRef(this));
    }
  }
  Object.defineProperty(TrackedPeerConnection, "name", { value: "RTCPeerConnection" });
  window.RTCPeerConnection = TrackedPeerConnection;
}

/** One line per live peer connection: the selected route and its round-trip time. */
async function describeCallTransport(): Promise<string[]> {
  const lines: string[] = [];
  for (const ref of peers) {
    const pc = ref.deref();
    if (!pc) {
      peers.delete(ref);
      continue;
    }
    if (pc.connectionState === "closed") continue;
    const stats = await pc.getStats().catch(() => null);
    if (!stats) continue;
    const byId = new Map<string, Record<string, unknown>>();
    stats.forEach((report) => byId.set(report.id, report as Record<string, unknown>));
    // Which routes ICE found at all: no udp srflx means UDP never got an answer from the network.
    const counts = new Map<string, number>();
    for (const report of byId.values()) {
      if (report.type !== "local-candidate") continue;
      const key = `${report.candidateType}/${report.protocol}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const udpPairs = [...byId.values()].filter((r) => r.type === "candidate-pair" && byId.get(String(r.localCandidateId))?.protocol === "udp");
    const udpStates = udpPairs.map((r) => String(r.state)).join(",") || "none";
    lines.push(`peer ${pc.connectionState} found: ${[...counts].map(([k, n]) => `${k}×${n}`).join(" ") || "no local candidates"}; udp pairs: ${udpStates}`);
    const pair = [...byId.values()].find((r) => r.type === "candidate-pair" && (r.nominated || r.selected) && r.state === "succeeded");
    if (!pair) {
      lines.push(`peer ${pc.connectionState}, no selected route yet`);
      continue;
    }
    const local = byId.get(String(pair.localCandidateId));
    const remote = byId.get(String(pair.remoteCandidateId));
    const rtt = typeof pair.currentRoundTripTime === "number" ? `${Math.round(pair.currentRoundTripTime * 1000)} ms` : "?";
    lines.push(
      `peer ${pc.connectionState}: local ${local?.candidateType}/${local?.protocol}${local?.relayProtocol ? ` (relay over ${local.relayProtocol})` : ""} → remote ${remote?.candidateType}/${remote?.protocol} ${remote?.address ?? ""}, round trip ${rtt}`,
    );
  }
  return lines;
}

function install(): void {
  const sampleRatesFixed = fixIgnoredSampleRates();
  trackPeerConnections();
  const nativeConnect = AudioNode.prototype.connect as unknown as Connect;
  const nativeDisconnect = AudioNode.prototype.disconnect as unknown as Disconnect;
  const nativeStop = MediaStreamTrack.prototype.stop;

  /** Nodes WhatsApp routes to the speakers, per context: the other side of the call. */
  const playback = new Map<BaseAudioContext, Set<AudioNode>>();
  let armedCallId: string | null = null;
  /** The armed call's microphone is the rig's voice: an agent call, or a rep call. */
  let armedAgent = false;
  /** The armed call is a rep call through AgentSDR's relay. */
  let armedRelay = false;
  /** Play the agent's voice on this machine's speakers too — for a rep at the laptop, not a cloud station. */
  let armedMonitor = true;
  let agentRig: AgentRig | null = null;
  let session: Session | null = null;
  /** A call whose recording is being stopped and handed over (end() until "recording" is posted). */
  let finishingCallId: string | null = null;
  /** The call whose screen was last reported as shown, so it is reported once. */
  let callUiShownFor: string | null = null;

  function noteCallUi(callId: string): void {
    if (callUiShownFor === callId) return;
    callUiShownFor = callId;
    post({ source: HOOK_SOURCE, type: "call-ui", callId });
  }

  // --- instrumentation -------------------------------------------------------

  // Arguments pass through exactly as WhatsApp gave them: connect() is
  // overloaded (AudioNode, output, input) / (AudioParam, output), and an
  // extra trailing argument would steer Chrome to the wrong overload.
  AudioNode.prototype.connect = function (this: AudioNode, ...args: unknown[]) {
    const result = (nativeConnect as unknown as (...rest: unknown[]) => unknown).apply(this, args);
    const destination = args[0];
    if (destination instanceof AudioDestinationNode) {
      rememberPlayback(this);
      if (session) tap(session, this);
    }
    return result;
  } as unknown as typeof AudioNode.prototype.connect;

  MediaStreamTrack.prototype.stop = function (this: MediaStreamTrack) {
    nativeStop.call(this);
    if (session && this === session.micTrack) micGone("WhatsApp stopped the microphone");
  };

  /**
   * The call's microphone stopped or ended: normally the call is over. On an
   * agent call WhatsApp may swap microphones mid-call, so while its call
   * screen is still up the call carries on — every microphone it gets is the
   * agent's voice — and the call UI or timer decides when it ends.
   */
  function micGone(why: string): void {
    const current = session;
    if (!current) return;
    if (agentRig?.callId === current.callId) {
      const stillUp = readCallUi().present;
      agentLog(`${why}; call screen ${stillUp ? "still up — carrying on" : "gone — ending"}`);
      if (stillUp) return;
    }
    end();
  }

  const mediaDevices = navigator.mediaDevices;
  if (mediaDevices?.getUserMedia) {
    const getUserMedia = mediaDevices.getUserMedia.bind(mediaDevices);
    mediaDevices.getUserMedia = async (constraints?: MediaStreamConstraints) => {
      // The real microphone is still asked for, so WhatsApp's permission
      // flow is unchanged; on an agent call WhatsApp gets the agent's voice
      // instead — for every microphone it asks for until the call is over.
      const agentCallId = agentRig?.callId ?? (armedAgent ? armedCallId : null);
      let stream: MediaStream;
      try {
        stream = await getUserMedia(constraints);
      } catch (error) {
        // A cloud browser may have no audio input at all (GoLogin's Cloud
        // Browser: "Requested device not found", 12 Oct 2026). An agent call
        // never uses the real microphone, so it goes ahead without one.
        if (!agentCallId || !constraints?.audio) throw error;
        agentLog(`no real microphone (${describe(error)}); the agent's voice is the only one`);
        stream = new MediaStream();
      }
      if (agentCallId && (stream.getAudioTracks().length > 0 || constraints?.audio)) stream = agentMicrophone(agentCallId, stream);
      const track = stream.getAudioTracks()[0];
      if (track) setTimeout(() => begin(track), MIC_SETTLE_MS);
      return stream;
    };
  }

  // WhatsApp checks for a microphone before it offers or places a call. On
  // an agent call with no audio input in the machine, it is shown one.
  if (mediaDevices?.enumerateDevices) {
    const enumerateDevices = mediaDevices.enumerateDevices.bind(mediaDevices);
    mediaDevices.enumerateDevices = async () => {
      const devices = await enumerateDevices();
      const agentCallId = agentRig?.callId ?? (armedAgent ? armedCallId : null);
      if (!agentCallId || devices.some((device) => device.kind === "audioinput")) return devices;
      const agentInput = {
        deviceId: "agentsdr-agent",
        groupId: "agentsdr-agent",
        kind: "audioinput",
        label: "AgentSDR agent",
        toJSON() {
          return { deviceId: this.deviceId, groupId: this.groupId, kind: this.kind, label: this.label };
        },
      } as MediaDeviceInfo;
      return [...devices, agentInput];
    };
  }

  window.addEventListener("message", (event: MessageEvent) => {
    if (event.source !== window) return;
    const data = event.data as Partial<AgentToHook> | null;
    if (data?.source !== AGENT_SOURCE) return;
    if (data.type === "arm" && data.callId) {
      const agent = data.agent === true;
      // A rep call never has an agent too.
      arm(data.callId, agent, data.monitor !== false, data.repRelay === true && !agent);
    }
    else if (data.type === "disarm") {
      armedCallId = null;
      if (!session) dropAgentRig();
    }
    else if (data.type === "agent-play" || data.type === "agent-interrupt" || data.type === "agent-hangup") {
      // The agent's voice and controls, for the agent call this tab is on.
      const rig = agentRig;
      if (!rig || data.callId !== rig.callId) return;
      if (data.type === "agent-play" && data.pcm) agentPlay(rig, data.pcm, data.rate ?? 24_000);
      else if (data.type === "agent-interrupt") agentSilence(rig);
      else if (data.type === "agent-hangup") agentHangup(rig);
    }
    else if (data.type === "resume-audio") resumeAudio();
    // Station mode answering an incoming call: wa-agent armed this tab first.
    else if (data.type === "accept-call" && data.callId) void acceptIncoming(data.callId);
    else if (data.type === "probe") post({ source: HOOK_SOURCE, type: "probe-result", callId: session?.callId ?? finishingCallId });
    else if (data.type === "end-call" && data.callId) {
      // Hang up with WhatsApp's own button; if the call is already over
      // there (hung up in WhatsApp, unseen), close it out here instead.
      const button = readCallUi().endButton;
      if (button) button.click();
      else if (session) end();
      else if (armedCallId) reportNotAnswered();
      post({ source: HOOK_SOURCE, type: "end-result", callId: data.callId, clicked: true });
    }
  });

  // --- before the call picks up the microphone --------------------------------
  // A call hung up while still "Calling…" may never open the microphone, so
  // there is no session to end. Watching the call UI from the moment the call
  // is armed catches it: seen, then gone, is a call that ended unanswered.

  let armedAt = 0;
  let armWatch = 0;
  let armSawCallUi = false;
  let armCallUiMissing = 0;

  function arm(callId: string, agent: boolean, monitor: boolean, relay: boolean): void {
    // A session whose call ended unseen would block this call's session.
    if (session && !readCallUi().present) end();
    if (!session) dropAgentRig();
    armedCallId = callId;
    armedAgent = agent || relay;
    armedRelay = relay;
    armedMonitor = monitor;
    armedAt = Date.now();
    armSawCallUi = false;
    armCallUiMissing = 0;
    window.clearInterval(armWatch);
    armWatch = window.setInterval(watchArmed, WATCH_INTERVAL_MS);
  }

  function watchArmed(): void {
    if (!armedCallId || session) {
      window.clearInterval(armWatch);
      return;
    }
    if (readCallUi().present) {
      noteCallUi(armedCallId);
      armSawCallUi = true;
      armCallUiMissing = 0;
    } else if (armSawCallUi) {
      armCallUiMissing += 1;
    }
    const neverPlaced = !armSawCallUi && Date.now() - armedAt > ARMED_WITHOUT_CALL_MS;
    if (armCallUiMissing >= END_BUTTON_GONE_CHECKS || neverPlaced) reportNotAnswered();
  }

  function reportNotAnswered(): void {
    const callId = armedCallId;
    armedCallId = null;
    window.clearInterval(armWatch);
    if (!session) dropAgentRig();
    if (callId) post({ source: HOOK_SOURCE, type: "not-answered", callId, dialedAt: armedAt, endedAt: Date.now() });
  }

  function rememberPlayback(node: AudioNode): void {
    for (const context of playback.keys()) if (context.state === "closed") playback.delete(context);
    const nodes = playback.get(node.context) ?? new Set<AudioNode>();
    nodes.add(node);
    playback.set(node.context, nodes);
  }

  // --- a call ----------------------------------------------------------------

  /** WhatsApp's microphone survived the settle delay: a call is dialing. */
  function begin(micTrack: MediaStreamTrack): void {
    if (!armedCallId || session || micTrack.readyState !== "live") return;
    const callId = armedCallId;
    let started: Recording | null = null;
    try {
      const rig = agentRig?.callId === callId ? agentRig : null;
      // An agent call's graph lives where its microphone track was made.
      const context = rig?.context ?? newestPlaybackContext() ?? new AudioContext();
      const remoteBus = context.createGain();
      const merger = context.createChannelMerger(2);
      const output = context.createMediaStreamDestination();
      const micClone = micTrack.clone();
      const micSource = context.createMediaStreamSource(new MediaStream([micClone]));

      // Started at once, on the output stream: the graph is wired below
      // within the same task, so nothing is missed.
      const recording = startRecording(output);
      started = recording;

      const next: Session = {
        callId,
        micTrack,
        micClone,
        context,
        remoteBus,
        output,
        links: [],
        bridges: new Map(),
        dialedAt: Date.now(),
        answeredAt: null,
        lastTimerText: null,
        timerSeen: false,
        timerStill: 0,
        sawEndButton: false,
        endButtonMissing: 0,
        lastStatusText: null,
        lastWhere: null,
        recording,
        watch: 0,
      };
      // Each merger input is downmixed to mono: the rep left, the lead right.
      link(next, leveled(next, micSource), merger, 0);
      link(next, leveled(next, remoteBus), merger, 1);
      link(next, merger, output);
      if (rig) captureLead(next, rig);
      for (const [playbackContext, nodes] of playback) {
        if (playbackContext.state !== "closed") for (const node of nodes) tap(next, node);
      }

      session = next;
      micTrack.addEventListener("ended", () => { if (session?.micTrack === micTrack) micGone("the microphone track ended"); });
      if (rig) {
        agentLog(`call session started; audio context ${context.state} at ${context.sampleRate} Hz`);
        if (sampleRatesFixed) {
          const asked = [...ignoredRateRequests].join(", ") || "none so far";
          agentLog(`this browser ignores AudioContext sample rates; contexts made at the default rate (WhatsApp asked for: ${asked} Hz)`);
        }
      }
      next.watch = window.setInterval(watch, WATCH_INTERVAL_MS);
      post({ source: HOOK_SOURCE, type: "dialing", callId });
      setTimeout(checkSuspended, 1500);
    } catch (error) {
      armedCallId = null;
      try {
        if (started && started.recorder.state !== "inactive") started.recorder.stop();
      } catch {
        // Nothing to keep; the call is reported failed below.
      }
      post({ source: HOOK_SOURCE, type: "recording-failed", callId, error: describe(error) });
    }
  }

  function watch(): void {
    const current = session;
    if (!current) return;
    const ui = readCallUi();
    const { timerText, statusText } = ui;
    if (ui.present) {
      noteCallUi(current.callId);
      current.sawEndButton = true;
      current.endButtonMissing = 0;
    } else if (current.sawEndButton) {
      current.endButtonMissing += 1;
    }
    const callUiGone = current.endButtonMissing >= END_BUTTON_GONE_CHECKS;
    if (ui.describe !== current.lastWhere) {
      current.lastWhere = ui.describe;
      post({ source: HOOK_SOURCE, type: "diag", callId: current.callId, text: ui.describe });
    }
    if (statusText && statusText !== current.lastStatusText) {
      current.lastStatusText = statusText;
      post({ source: HOOK_SOURCE, type: "call-status", callId: current.callId, text: statusText });
    }

    if (current.answeredAt === null) {
      // The call UI closed without the timer ever running: not answered.
      if (callUiGone) {
        if (agentRig?.callId === current.callId) agentLog("call screen gone before any pick-up was seen");
        return end();
      }
      const timerSeconds = timerText ? clockSeconds(timerText) : null;
      const pickedUp =
        timerText !== null &&
        (ui.inPip ||
          (timerSeconds !== null && timerSeconds <= FRESH_TIMER_SECONDS) ||
          (current.lastTimerText !== null && timerText !== current.lastTimerText));
      if (pickedUp) {
        // The timer counts from the pick-up: a 0:02 when noticed means about
        // two and a half seconds ago.
        const now = Date.now();
        answer(current, true, Math.max(current.recording.startedAt, now - (timerSeconds ?? 0) * 1000 - 500));
      } else if (Date.now() - current.dialedAt > NO_TIMER_FALLBACK_MS && !STILL_RINGING.test(statusText ?? "")) {
        // No timer seen in a minute — WhatsApp's markup may have changed, so
        // keep the recording rather than discard the call. Not while WhatsApp
        // itself still says "Calling…"/"Ringing…": that is a long ring.
        answer(current, false, current.recording.startedAt);
      }
      current.lastTimerText = timerText;
      return;
    }

    if (callUiGone) {
      if (agentRig?.callId === current.callId) agentLog("call screen gone — ending");
      return end();
    }
    // A running call's timer ticks every second. Where it can be trusted to
    // (see CallUi.timerTrusted), one that stops moving, or disappears, for
    // a few checks means the call ended — hung up anywhere, even when a stale
    // End call lingers on the page.
    if (current.timerSeen && ui.timerTrusted) {
      if (timerText && timerText !== current.lastTimerText) {
        current.lastTimerText = timerText;
        current.timerStill = 0;
      } else {
        current.timerStill += 1;
      }
      if (current.timerStill >= TIMER_GONE_CHECKS) {
        if (agentRig?.callId === current.callId) agentLog(`call timer stopped at ${current.lastTimerText ?? "?"} — ending`);
        end();
      }
    }
  }

  /**
   * The lead picked up at `answeredAt`. The recorder is already running; this
   * only dates the pick-up, from the timer's reading or — without one — as
   * the start of the recording, so the whole of it is kept as the call.
   * `timerSeen` also decides how the call's end is recognised (see watch).
   */
  function answer(current: Session, timerSeen: boolean, answeredAt: number): void {
    current.answeredAt = answeredAt;
    if (agentRig?.callId === current.callId) {
      agentRig.listening = true;
      agentLog(`picked up (${timerSeen ? "timer seen" : "no timer — fallback"})`);
      // A moment for the route's round trip to be measured.
      window.setTimeout(() => {
        void describeCallTransport().then((lines) => {
          if (!lines.length) agentLog("call transport: no WebRTC peer connection seen");
          for (const line of lines) agentLog(`call transport: ${line}`);
        });
      }, 2_000);
    }
    current.timerSeen = timerSeen;
    post({ source: HOOK_SOURCE, type: "answered", callId: current.callId, answeredAt, timerSeen });
  }

  /** Records the call's stereo mix, in one-second chunks, from now until end(). */
  function startRecording(output: MediaStreamAudioDestinationNode): Recording {
    const recorder = new MediaRecorder(output.stream, { mimeType: recordingMimeType() });
    const recording: Recording = { recorder, chunks: [], startedAt: Date.now() };
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) recording.chunks.push(event.data);
    };
    recorder.start(1000);
    return recording;
  }

  function end(): void {
    const current = session;
    if (!current) return;
    session = null;
    armedCallId = null; // one call per arming
    window.clearInterval(current.watch);
    const endedAt = Date.now();

    const recording = current.recording;
    const answeredAt = current.answeredAt;
    if (answeredAt === null) {
      // Never picked up: the ringing recorded so far is discarded.
      recording.recorder.ondataavailable = null;
      try {
        if (recording.recorder.state !== "inactive") recording.recorder.stop();
      } catch {
        // Already stopped; there is nothing to keep either way.
      }
      cleanup(current);
      post({ source: HOOK_SOURCE, type: "not-answered", callId: current.callId, dialedAt: current.dialedAt, endedAt });
      return;
    }
    finishingCallId = current.callId;
    let handedOver = false;
    const handOver = () => {
      if (handedOver) return;
      handedOver = true;
      cleanup(current);
      const blob = new Blob(recording.chunks, { type: recording.recorder.mimeType || recordingMimeType() });
      post({
        source: HOOK_SOURCE,
        type: "recording",
        callId: current.callId,
        blob,
        startedAt: recording.startedAt,
        answeredAt,
        endedAt,
      });
      // Kept a moment past the hand-over, so a probe landing before wa-agent
      // has started the upload still sees the call as busy.
      setTimeout(() => {
        if (finishingCallId === current.callId) finishingCallId = null;
      }, 2_000);
    };
    // A recorder Chrome already stopped (its source ended, or it errored)
    // has nothing left to flush and would throw on stop(): hand over what it
    // recorded instead of losing it.
    if (recording.recorder.state === "inactive") return handOver();
    recording.recorder.onstop = handOver;
    try {
      recording.recorder.stop();
    } catch {
      handOver();
    }
  }

  function cleanup(current: Session): void {
    if (agentRig?.callId === current.callId) dropAgentRig();
    nativeStop.call(current.micClone);
    for (const [from, to] of current.links) {
      try {
        nativeDisconnect.call(from, to);
      } catch {
        // Already gone with its context.
      }
    }
  }

  // --- the recording graph ---------------------------------------------------

  /** Feeds one of WhatsApp's speaker-bound nodes into the recording too. */
  function tap(current: Session, node: AudioNode): void {
    const source = node.context;
    if (source.state === "closed") return;
    if (source === current.context) return link(current, node, current.remoteBus);
    if (!(source instanceof AudioContext)) return;
    // Nodes cannot connect across contexts; a MediaStream can carry audio between them.
    let bridge = current.bridges.get(source);
    if (!bridge) {
      bridge = source.createMediaStreamDestination();
      current.bridges.set(source, bridge);
      link(current, current.context.createMediaStreamSource(bridge.stream), current.remoteBus);
    }
    link(current, node, bridge);
  }

  function link(current: Session, from: AudioNode, to: AudioNode, input?: number): void {
    nativeConnect.call(from, to, 0, input ?? 0);
    current.links.push([from, to]);
  }

  /**
   * Evens out one speaker's loudness in the recording (not in what the rep
   * hears): the raw mic sat ~6 dB above the call audio in the first tests.
   */
  function leveled(current: Session, source: AudioNode): AudioNode {
    const compressor = new DynamicsCompressorNode(current.context, {
      threshold: -40,
      knee: 20,
      ratio: 4,
      attack: 0.01,
      release: 0.25,
    });
    link(current, source, compressor);
    return compressor;
  }

  function newestPlaybackContext(): AudioContext | null {
    let newest: AudioContext | null = null;
    for (const context of playback.keys()) {
      if (context instanceof AudioContext && context.state !== "closed") newest = context;
    }
    return newest;
  }

  // --- the AI voice agent (trial) ---------------------------------------------

  /**
   * The microphone WhatsApp gets on an agent call: the agent's voice, with
   * the real microphone released. Any video tracks pass through untouched.
   */
  function agentMicrophone(callId: string, real: MediaStream): MediaStream {
    try {
      const rig = ensureAgentRig(callId);
      // Capturing now, the page may run it.
      if (rig.context.state === "suspended") void rig.context.resume();
      const destination = rig.context.createMediaStreamDestination();
      nativeConnect.call(rig.voice, destination, 0, 0);
      for (const track of real.getAudioTracks()) {
        track.enabled = false;
        rig.held.push(track);
      }
      const [fake] = destination.stream.getAudioTracks();
      const whose = rig.relay ? "the rep's" : "the agent's";
      agentLog(`WhatsApp asked for the microphone; gave it ${whose} voice (context ${rig.context.state})`);
      return new MediaStream([fake, ...real.getVideoTracks()]);
    } catch (error) {
      // Better the rep's own voice than a dead call.
      console.warn("[agentsdr agent] could not make the agent's microphone; using the real one", error);
      return real;
    }
  }

  function ensureAgentRig(callId: string): AgentRig {
    if (agentRig?.callId === callId) return agentRig;
    dropAgentRig();
    // A context of its own: one of WhatsApp's may be closed under it (the
    // ringing sound's, at the pick-up), which would end the microphone track.
    const context = new AudioContext();
    if (context.state === "suspended") void context.resume();
    const voice = context.createGain();
    // The rep hears the agent too. Native connect: this is not WhatsApp's
    // playback, so it must not be tapped as the lead's side.
    // On a cloud station nobody listens here, and a phone near the speakers
    // would send the agent's voice back into the call as the lead's.
    if (armedMonitor) nativeConnect.call(voice, context.destination, 0, 0);
    context.addEventListener("statechange", () => {
      if (agentRig?.context === context) agentLog(`agent audio context is now ${context.state}`);
    });
    agentRig = {
      callId,
      relay: armedRelay,
      context,
      voice,
      queued: new Set(),
      playHead: 0,
      listening: false,
      hangupTimer: 0,
      held: [],
      sentAudio: false,
      playedAudio: false,
      catchUps: 0,
    };
    return agentRig;
  }

  function dropAgentRig(): void {
    const rig = agentRig;
    if (!rig) return;
    agentRig = null;
    window.clearTimeout(rig.hangupTimer);
    agentSilence(rig);
    for (const track of rig.held) nativeStop.call(track);
    try {
      nativeDisconnect.call(rig.voice, rig.context.destination);
    } catch {
      // Gone with its context.
    }
  }

  /**
   * Sends the lead's side (remoteBus) to wa-agent as 16 kHz mono PCM: for the
   * agent once they have picked up (agent-audio), for a rep call from dialing
   * on, ringing included (relay-audio).
   */
  function captureLead(current: Session, rig: AgentRig): void {
    const processor = current.context.createScriptProcessor(rig.relay ? RELAY_CAPTURE_FRAMES : AGENT_CAPTURE_FRAMES, 1, 1);
    const sink = current.context.createMediaStreamDestination();
    const rate = rig.relay ? REP_RELAY_SAMPLE_RATE : AGENT_INPUT_RATE;
    // Filtered and continuous across blocks — see downsample.ts for what the
    // old nearest-sample pick did to the lead's voice.
    const downsample = createDownsampler(current.context.sampleRate, rate);
    processor.onaudioprocess = (event) => {
      if ((!rig.relay && !rig.listening) || agentRig !== rig) return;
      if (!rig.sentAudio) {
        rig.sentAudio = true;
        agentLog(`sending the lead's audio to ${rig.relay ? "the rep" : "the agent"} (${current.context.sampleRate} Hz → ${rate} Hz)`);
      }
      const pcm = downsample(event.inputBuffer.getChannelData(0));
      if (pcm.length === 0) return;
      window.postMessage(
        { source: HOOK_SOURCE, type: rig.relay ? "relay-audio" : "agent-audio", callId: rig.callId, pcm: pcm.buffer } satisfies HookToAgent,
        location.origin,
        [pcm.buffer],
      );
    };
    // A ScriptProcessor only runs while something pulls it; a stream
    // destination does, without sending anything to the speakers.
    link(current, current.remoteBus, processor);
    link(current, processor, sink);
  }

  /**
   * Queues a chunk of the agent's voice (mono 16-bit PCM) after what is
   * already playing. A rep call's arrives over the network in small chunks:
   * after a gap it starts REP_RELAY_JITTER_MS late, to ride out the next
   * one, and more than REP_RELAY_MAX_BUFFER_MS queued is dropped, so a stall
   * leaves the rep heard late for a moment, not for the rest of the call.
   */
  function agentPlay(rig: AgentRig, data: ArrayBuffer, rate: number): void {
    const samples = new Int16Array(data);
    if (samples.length === 0) return;
    if (!rig.playedAudio) {
      rig.playedAudio = true;
      agentLog(`playing ${rig.relay ? "the rep's" : "the agent's"} voice into the call (context ${rig.context.state})`);
    }
    if (rig.relay && rig.playHead - rig.context.currentTime > REP_RELAY_MAX_BUFFER_MS / 1000) {
      agentSilence(rig);
      rig.catchUps += 1;
      // The first, then every 20th: a network that keeps stalling shows without flooding the log.
      if (rig.catchUps % 20 === 1) agentLog(`the rep's audio fell behind; dropped what was queued to catch up (${rig.catchUps}×)`);
    }
    const buffer = rig.context.createBuffer(1, samples.length, rate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 0x8000;
    const source = rig.context.createBufferSource();
    source.buffer = buffer;
    nativeConnect.call(source, rig.voice, 0, 0);
    const lead = rig.relay ? REP_RELAY_JITTER_MS / 1000 : AGENT_PLAY_LEAD_S;
    const startAt = Math.max(rig.context.currentTime + lead, rig.playHead);
    source.start(startAt);
    rig.playHead = startAt + buffer.duration;
    rig.queued.add(source);
    source.onended = () => rig.queued.delete(source);
  }

  function agentSilence(rig: AgentRig): void {
    for (const source of rig.queued) {
      try {
        source.stop();
      } catch {
        // Never started or already ended.
      }
    }
    rig.queued.clear();
    rig.playHead = 0;
  }

  /** A step of an agent call (or a rep call): in this tab's console, and in AgentSDR's timing table. */
  function agentLog(text: string): void {
    const who = (agentRig?.relay ?? armedRelay) ? "rep relay" : "agent";
    console.info(`[agentsdr ${who}]`, text);
    const callId = agentRig?.callId ?? session?.callId ?? armedCallId;
    if (callId) post({ source: HOOK_SOURCE, type: "diag", callId, text: `${who}: ${text}` });
  }

  /** Presses End call once the agent's goodbye has finished playing. */
  function agentHangup(rig: AgentRig): void {
    const remainingMs = Math.max(0, rig.playHead - rig.context.currentTime) * 1000;
    window.clearTimeout(rig.hangupTimer);
    rig.hangupTimer = window.setTimeout(() => {
      const button = readCallUi().endButton;
      if (button) button.click();
      else if (session) end();
    }, remainingMs + AGENT_HANGUP_GRACE_MS);
  }

  // --- audio that Chrome's autoplay policy held back --------------------------

  function checkSuspended(): void {
    const current = session;
    if (!current) return;
    const contexts = [current.context, ...playback.keys()];
    if (contexts.some((context) => context.state === "suspended")) {
      post({ source: HOOK_SOURCE, type: "audio-suspended", callId: current.callId });
    }
  }

  function resumeAudio(): void {
    const contexts = new Set<BaseAudioContext>(playback.keys());
    if (session) contexts.add(session.context);
    for (const context of contexts) {
      if (context instanceof AudioContext && context.state === "suspended") void context.resume();
    }
  }
}

/** The documents a call's UI can be in: the page, and WhatsApp's picture-in-picture window. */
function callDocuments(): Document[] {
  const documents: Document[] = [document];
  try {
    const pip = (window as unknown as { documentPictureInPicture?: { window: Window | null } }).documentPictureInPicture
      ?.window;
    if (pip && pip.document !== document) documents.push(pip.document);
  } catch {
    // No picture-in-picture support, or the window just closed.
  }
  return documents;
}

type CallUi = {
  /** The call UI is showing somewhere — End call found, or WhatsApp's picture-in-picture window open. */
  present: boolean;
  endButton: HTMLElement | null;
  timerText: string | null;
  statusText: string | null;
  /** A short account of what was found, for diagnosis. */
  describe: string;
  /** The call UI is WhatsApp's picture-in-picture window, which holds nothing but the call. */
  inPip: boolean;
  /**
   * Whether the timer is on screen and so keeps ticking: the picture-in-
   * picture window, or the page while its tab is visible. A hidden page may
   * render lazily, so its timer is not evidence either way.
   */
  timerTrusted: boolean;
};

/**
 * Reads the call UI, preferring WhatsApp's picture-in-picture window. On 29
 * Sep 2026 a call answered after it moved there was never seen as answered:
 * the page went on showing an End call but no running timer, so the page's
 * copy is not to be trusted once that window is open. That window holds nothing but the
 * call, so its whole text is searched for the timer; on the page the search
 * stays next to End call, away from voice-note durations in the chat.
 */
function readCallUi(): CallUi {
  const pip = callDocuments()[1] ?? null;
  if (pip?.body) {
    const texts = textsIn(pip.body);
    const endButton = findEndButtonIn(pip) ?? findEndButtonIn(document);
    const labels = Array.from(pip.querySelectorAll("[aria-label]"))
      .map((element) => element.getAttribute("aria-label"))
      .filter(Boolean)
      .slice(0, 12);
    return {
      present: true,
      inPip: true,
      timerTrusted: true,
      endButton,
      timerText: texts.find((text) => TIMER_PATTERN.test(text)) ?? null,
      statusText: texts.find((text) => STATUS_PATTERN.test(text)) ?? null,
      describe: `call UI in picture-in-picture; End call ${endButton ? "found" : "NOT found"}; labels: ${labels.join(" | ") || "none"}`,
    };
  }
  const endButton = findEndButtonIn(document);
  return {
    present: Boolean(endButton),
    inPip: false,
    timerTrusted: document.visibilityState === "visible",
    endButton,
    timerText: endButton ? findTimerText(endButton) : null,
    statusText: endButton ? findStatusText(endButton) : null,
    describe: endButton ? "call UI in the WhatsApp page" : "no call UI found",
  };
}

function findEndButtonIn(doc: Document): HTMLElement | null {
  for (const element of Array.from(doc.querySelectorAll<HTMLElement>("button[aria-label], [role='button'][aria-label]"))) {
    if (END_CALL_LABEL.test(element.getAttribute("aria-label") ?? "")) return element;
  }
  for (const icon of Array.from(doc.querySelectorAll<HTMLElement>("[data-icon]"))) {
    if (END_CALL_ICON.test(icon.getAttribute("data-icon") ?? "")) {
      return icon.closest<HTMLElement>("button, [role='button']") ?? icon;
    }
  }
  return null;
}

function textsIn(root: HTMLElement): string[] {
  const texts: string[] = [];
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent?.trim();
    if (text) texts.push(text);
  }
  return texts;
}

/** The call timer's current text near End call, or null. */
function findTimerText(endButton: HTMLElement): string | null {
  let container: HTMLElement | null = endButton.parentElement;
  while (container) {
    const walker = container.ownerDocument.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim() ?? "";
      if (TIMER_PATTERN.test(text)) return text;
    }
    const parent: HTMLElement | null = container.parentElement;
    if (!parent || parent.getElementsByTagName("*").length > MAX_TIMER_SEARCH_ELEMENTS) return null;
    container = parent;
  }
  return null;
}

/** WhatsApp's own call-state line near End call ("Calling…", "Ringing…"), for timing. */
function findStatusText(endButton: HTMLElement): string | null {
  let container: HTMLElement | null = endButton.parentElement;
  while (container) {
    const walker = container.ownerDocument.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim() ?? "";
      if (STATUS_PATTERN.test(text)) return text;
    }
    const parent: HTMLElement | null = container.parentElement;
    if (!parent || parent.getElementsByTagName("*").length > MAX_TIMER_SEARCH_ELEMENTS) return null;
    container = parent;
  }
  return null;
}

/** Seconds shown by a call timer: "0:07" → 7, "1:02:03" → 3723. */
function clockSeconds(text: string): number | null {
  const parts = text.split(":").map(Number);
  if (parts.length < 2 || parts.some((part) => !Number.isFinite(part))) return null;
  return parts.reduce((total, part) => total * 60 + part, 0);
}

/** Ogg/Opus where Chrome can record it, else WebM; transcription accepts both. */
function recordingMimeType(): string {
  const ogg = "audio/ogg;codecs=opus";
  return MediaRecorder.isTypeSupported(ogg) ? ogg : "audio/webm;codecs=opus";
}

function post(message: HookToAgent): void {
  window.postMessage(message, location.origin);
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// =============================================================================
// --- station messaging (calling stations only) --------------------------------
// =============================================================================
//
// Separate from the call recorder above and sharing nothing with it. On a
// calling station, wa-agent enables this (`messaging-enable`, sent only when
// the service worker's station mode asked for messages), and it then reads
// messages from WhatsApp Web's own message store — Meta's module system
// (`window.require`): WAWebCollections' Msg / Chat / Contact collections, and
// WAWebSocketModel's Socket.hasSynced for readiness, as whatsapp-web.js does.
// A rep's own WhatsApp Web is never read: nothing here runs until enabled.
//
// Every access to WhatsApp's modules is guarded; this must never throw into
// WhatsApp's code or disturb a call.

type WaRequire = (name: string) => unknown;
type WaWid = { user?: string; server?: string; _serialized?: string; toString(): string };
type WaMsg = {
  id?: { _serialized?: string; fromMe?: boolean; remote?: WaWid | string; id?: string };
  t?: number;
  type?: string;
  body?: unknown;
  caption?: unknown;
  notifyName?: string;
  isNewMsg?: boolean;
  once?: (event: string, listener: () => void) => void;
  off?: (event: string, listener: () => void) => void;
};
type WaCollection<T> = {
  on?: (event: string, listener: (model: T) => void) => void;
  get?: (id: unknown) => T | undefined;
  getModelsArray?: () => T[];
  models?: T[];
};
type WaChat = { id?: WaWid | string; t?: number; unreadCount?: number; msgs?: WaCollection<WaMsg> };
type WaContact = { name?: string; pushname?: string; verifiedName?: string };
type WaCollections = { Msg?: WaCollection<WaMsg>; Chat?: WaCollection<WaChat>; Contact?: WaCollection<WaContact> };

/** Tries every 2 s for the first five minutes after it is enabled, then every 30 s. */
const MESSAGING_ATTACH_POLL_MS = 2_000;
const MESSAGING_ATTACH_FAST_FOR_MS = 5 * 60_000;
const MESSAGING_ATTACH_SLOW_POLL_MS = 30_000;
/** A message still encrypted when added gets this long to decrypt. */
const MESSAGING_DECRYPT_WAIT_MS = 15_000;
/** At most this many unread messages per chat are read when the listener attaches. */
const MESSAGING_BACKFILL_PER_CHAT = 50;
/**
 * Besides the "add" event, the store is swept this often for messages newer
 * than the listener (less a margin): an incoming message the event missed, or
 * one WhatsApp did not flag isNewMsg, is still read. Duplicates are dropped
 * here (`emitted`) and again by the service worker and the server.
 */
const MESSAGING_SWEEP_MS = 5_000;
const MESSAGING_SWEEP_MARGIN_MS = 2 * 60_000;
/** Chats swept: those active since then, and their last messages only. */
const MESSAGING_SWEEP_PER_CHAT = 20;
const MESSAGING_EMITTED_MAX = 5_000;

const messaging = {
  enabled: false,
  enabledAt: 0,
  attached: false,
  attachedAt: 0,
  timer: 0,
  sweepTimer: 0,
  /** Message ids already passed on (or skipped), oldest first. */
  emitted: new Set<string>(),
  /** "add" events since the last status line: all of them, and those flagged new. */
  adds: 0,
  newAdds: 0,
};

const messagingScope = window as unknown as { __agentsdrMessaging?: boolean };
try {
  if (!messagingScope.__agentsdrMessaging) {
    messagingScope.__agentsdrMessaging = true;
    window.addEventListener("message", onMessagingRequest);
  }
} catch {
  // Messaging is optional; the call recorder above carries on regardless.
}

function onMessagingRequest(event: MessageEvent): void {
  try {
    if (event.source !== window) return;
    const data = event.data as Partial<AgentToHookMessaging> | null;
    if (data?.source !== AGENT_MESSAGING_SOURCE) return;
    if (data.type === "messaging-enable") enableMessaging();
    else if (data.type === "messaging-status") postMessagingSource();
    else if (data.type === "find-sent" && data.requestId) {
      postMessaging({
        source: HOOK_MESSAGING_SOURCE,
        type: "found-sent",
        requestId: data.requestId,
        providerMessageId: findSent(data.chatDigits ?? "", data.body ?? "", data.sinceMs ?? 0, data.keyId ?? null),
      });
    }
  } catch (error) {
    messagingLog(`request failed: ${describe(error)}`);
  }
}

function enableMessaging(): void {
  if (messaging.enabled) {
    postMessagingSource();
    return;
  }
  messaging.enabled = true;
  messaging.enabledAt = Date.now();
  postMessagingSource();
  tryAttachMessaging();
  startIncomingCalls();
}

function postMessagingSource(): void {
  postMessaging({ source: HOOK_MESSAGING_SOURCE, type: "messaging-source", capability: messaging.attached ? "store" : "none" });
}

/** Attaches the Msg listener once WhatsApp's modules are loaded and it has synced; otherwise tries again later. */
function tryAttachMessaging(): void {
  window.clearTimeout(messaging.timer);
  if (messaging.attached) return;
  try {
    const collections = waCollections();
    const socket = waModule<{ Socket?: { hasSynced?: boolean } }>("WAWebSocketModel")?.Socket;
    if (collections?.Msg?.on && socket?.hasSynced === true) {
      collections.Msg.on("add", onMsgAdded);
      messaging.attached = true;
      messaging.attachedAt = Date.now();
      const version = (window as unknown as { Debug?: { VERSION?: string } }).Debug?.VERSION ?? "unknown";
      messagingLog(`listening to WhatsApp's message store (WhatsApp Web ${version})`);
      postMessagingSource();
      backfillUnread(collections);
      messaging.sweepTimer = window.setInterval(sweepStore, MESSAGING_SWEEP_MS);
      return;
    }
  } catch (error) {
    messagingLog(`could not attach yet: ${describe(error)}`);
  }
  const fast = Date.now() - messaging.enabledAt < MESSAGING_ATTACH_FAST_FOR_MS;
  messaging.timer = window.setTimeout(tryAttachMessaging, fast ? MESSAGING_ATTACH_POLL_MS : MESSAGING_ATTACH_SLOW_POLL_MS);
}

function waRequire(): WaRequire | null {
  const candidate = (window as unknown as { require?: unknown }).require;
  return typeof candidate === "function" ? (candidate as WaRequire) : null;
}

/** One of WhatsApp's modules, or null when it is not (yet) defined. */
function waModule<T>(name: string): T | null {
  try {
    return (waRequire()?.(name) as T | undefined) ?? null;
  } catch {
    return null;
  }
}

function waCollections(): WaCollections | null {
  return waModule<WaCollections>("WAWebCollections");
}

function modelsOf<T>(collection: WaCollection<T> | null | undefined): T[] {
  try {
    return collection?.getModelsArray?.() ?? collection?.models ?? [];
  } catch {
    return [];
  }
}

function onMsgAdded(msg: WaMsg): void {
  try {
    messaging.adds++;
    if (msg?.isNewMsg) messaging.newAdds++;
    // Older messages are added too when a chat loads its history; a recent one counts even unflagged.
    const recent = typeof msg?.t === "number" && msg.t * 1000 >= messaging.attachedAt - MESSAGING_SWEEP_MARGIN_MS;
    if (!msg?.isNewMsg && !recent) return;
    noteCallLog(msg);
    if (msg.type !== "ciphertext") {
      emitMessages([msg], "event");
      return;
    }
    // Still being decrypted: it is read once its real type arrives.
    let done = false;
    const onDecrypted = () => {
      if (done) return;
      done = true;
      try {
        emitMessages([msg], "event");
      } catch {
        // never into WhatsApp's code
      }
    };
    msg.once?.("change:type", onDecrypted);
    window.setTimeout(() => {
      if (done) return;
      done = true;
      try {
        msg.off?.("change:type", onDecrypted);
      } catch {
        // ignore
      }
    }, MESSAGING_DECRYPT_WAIT_MS);
  } catch (error) {
    messagingLog(`a message could not be read: ${describe(error)}`);
  }
}

/** Unread messages already in the store when the listener attaches — those that came in while it was not listening. */
function backfillUnread(collections: WaCollections): void {
  try {
    const found: WaMsg[] = [];
    for (const chat of modelsOf(collections.Chat)) {
      const unread = Math.min(chat?.unreadCount ?? 0, MESSAGING_BACKFILL_PER_CHAT);
      if (unread <= 0 || isNonPersonalJid(widString(chat.id))) continue;
      found.push(...modelsOf(chat.msgs).filter((msg) => msg?.id?.fromMe === false).slice(-unread));
    }
    if (found.length) {
      messagingLog(`read ${found.length} unread message(s) already in the store`);
      emitMessages(found, "backfill");
    }
  } catch (error) {
    messagingLog(`could not read unread chats: ${describe(error)}`);
  }
}

/** Messages newer than the listener (less the margin), from the global store and recently active chats. */
function sweepStore(): void {
  try {
    const collections = waCollections();
    if (!collections) return;
    const since = (messaging.attachedAt - MESSAGING_SWEEP_MARGIN_MS) / 1000;
    const isRecent = (msg: WaMsg | undefined) => typeof msg?.t === "number" && msg.t >= since;
    const found = modelsOf(collections.Msg).filter(isRecent);
    for (const chat of modelsOf(collections.Chat)) {
      if (typeof chat?.t === "number" && chat.t < since) continue;
      found.push(...modelsOf(chat?.msgs).slice(-MESSAGING_SWEEP_PER_CHAT).filter(isRecent));
    }
    // Still encrypted: left for a later sweep, once it has its real type.
    emitMessages(found.filter((msg) => msg?.type !== "ciphertext"), "sweep");
    if (messaging.adds) {
      messagingLog(`store: ${messaging.adds} message event(s), ${messaging.newAdds} flagged new`);
      messaging.adds = 0;
      messaging.newAdds = 0;
    }
  } catch (error) {
    messagingLog(`sweep failed: ${describe(error)}`);
  }
}

/** Passes each message on once (by id), and says why one is not kept. */
function emitMessages(msgs: WaMsg[], via: "event" | "sweep" | "backfill"): void {
  const messages: StationInboundMessage[] = [];
  for (const msg of msgs) {
    try {
      const id = msgId(msg);
      if (!id) {
        // Said once per message: the sweep sees it again every few seconds.
        if (!idlessLogged.has(msg)) {
          idlessLogged.add(msg);
          messagingLog(`${via}: a ${msg?.type ?? "?"} message has no id; skipped`);
        }
        continue;
      }
      if (messaging.emitted.has(id)) continue;
      messaging.emitted.add(id);
      if (messaging.emitted.size > MESSAGING_EMITTED_MAX) {
        const oldest = messaging.emitted.values().next().value;
        if (oldest !== undefined) messaging.emitted.delete(oldest);
      }
      const message = readStoreMessage(msg);
      if (message) messages.push(message);
      else messagingLog(`${via}: skipped a ${msg.type ?? "?"} message in a ${jidKind(widString(msg.id?.remote))} chat`);
    } catch (error) {
      messagingLog(`${via}: a message could not be read: ${describe(error)}`);
    }
  }
  if (!messages.length) return;
  const unknownNumber = messages.filter((message) => !message.chatPhone).length;
  messagingLog(
    `${via}: passing on ${messages.length} message(s) (${messages.filter((m) => m.direction === "inbound").length} received` +
      `${unknownNumber ? `, ${unknownNumber} without a known number` : ""})`,
  );
  postMessaging({ source: HOOK_MESSAGING_SOURCE, type: "messages", messages });
}

const idlessLogged = new WeakSet<WaMsg>();

/** A message's serialized id ("false_<chat jid>_<key id>"), however this WhatsApp Web version carries it. */
function msgId(msg: WaMsg | null | undefined): string | null {
  const key = msg?.id;
  if (!key) return null;
  let text: unknown = null;
  try {
    text = typeof key.toString === "function" ? key.toString() : null;
  } catch {
    // built from its parts below
  }
  return serializedMessageId({ serialized: key._serialized, text, fromMe: key.fromMe, remoteJid: widString(key.remote), keyId: key.id });
}

/** The kind of chat, for logs only (never the number). */
function jidKind(jid: string | null): string {
  const server = jid?.split("@")[1];
  return server ? `@${server}` : "unknown";
}

function readStoreMessage(msg: WaMsg): StationInboundMessage | null {
  const remote = msg.id?.remote;
  const chatJid = widString(remote);
  if (!chatJid || isNonPersonalJid(chatJid)) return null;
  const fromMe = msg.id?.fromMe === true;
  return storeMessage({
    id: msgId(msg),
    fromMe,
    chatJid,
    lidPhone: chatJid.endsWith("@lid") ? lidToPhoneDigits(remote) : null,
    t: typeof msg.t === "number" ? msg.t : null,
    type: msg.type ?? null,
    body: msg.body,
    caption: msg.caption,
    // For a message from this number, notifyName is this number's own name.
    chatName: contactName(remote) ?? (fromMe ? null : (msg.notifyName ?? null)),
  });
}

/** A Wid (or jid string) as "<user>@<server>". */
function widString(wid: WaWid | string | null | undefined): string | null {
  if (!wid) return null;
  if (typeof wid === "string") return wid.includes("@") ? wid : null;
  if (typeof wid._serialized === "string" && wid._serialized.includes("@")) return wid._serialized;
  if (wid.user && wid.server) return `${wid.user}@${wid.server}`;
  const text = typeof wid.toString === "function" ? wid.toString() : "";
  return text.includes("@") ? text : null;
}

function asWid(wid: WaWid | string | null | undefined): WaWid | null {
  if (!wid) return null;
  if (typeof wid !== "string") return wid;
  try {
    return waModule<{ createWid?: (jid: string) => WaWid }>("WAWebWidFactory")?.createWid?.(wid) ?? null;
  } catch {
    return null;
  }
}

/** The number behind a "@lid" chat, from WhatsApp's in-memory lid↔phone map — digits, or null when it is not known. */
function lidToPhoneDigits(remote: WaWid | string | null | undefined): string | null {
  const wid = asWid(remote);
  if (!wid) return null;
  const lookups: (() => unknown)[] = [
    () => waModule<{ getPhoneNumber?: (wid: WaWid) => unknown }>("WAWebApiContact")?.getPhoneNumber?.(wid),
    () => waModule<{ toPn?: (wid: WaWid) => unknown }>("WAWebLidMigrationUtils")?.toPn?.(wid),
  ];
  for (const lookup of lookups) {
    try {
      const found = lookup() as WaWid | string | null | undefined;
      const jid = widString(found);
      const digits = jid && /@(c\.us|s\.whatsapp\.net)$/.test(jid) ? jid.split("@")[0].replace(/\D/g, "") : "";
      if (digits.length >= 6) return digits;
    } catch {
      // try the next
    }
  }
  return null;
}

function contactName(remote: WaWid | string | null | undefined): string | null {
  try {
    const contact = waCollections()?.Contact?.get?.(remote);
    return contact?.name || contact?.pushname || contact?.verifiedName || null;
  } catch {
    return null;
  }
}

/**
 * The id of a message just sent from this number: by its key id when wa-agent
 * read one from the page, else the newest one to `chatDigits` with this body
 * since `sinceMs`.
 */
function findSent(chatDigits: string, body: string, sinceMs: number, keyId: string | null): string | null {
  const collections = waCollections();
  if (!collections) return null;
  const candidates = [...modelsOf(collections.Msg)];
  try {
    const chat = collections.Chat?.get?.(`${chatDigits}@c.us`);
    candidates.push(...modelsOf(chat?.msgs));
  } catch {
    // the Msg collection alone
  }
  const wanted = normalizeBody(body);
  let best: { id: string; t: number } | null = null;
  for (const msg of candidates) {
    try {
      const id = msgId(msg);
      if (!id || msg.id?.fromMe !== true) continue;
      if (keyId && (msg.id.id === keyId || parseMessageId(id)?.keyId === keyId)) return id;
      const t = (msg.t ?? 0) * 1000;
      if (t < sinceMs || normalizeBody(msg.body) !== wanted) continue;
      const jid = widString(msg.id.remote) ?? "";
      const digits = jid.endsWith("@lid") ? lidToPhoneDigits(msg.id.remote) : jid.split("@")[0];
      if (digits !== chatDigits) continue;
      if (!best || t >= best.t) best = { id, t };
    } catch {
      // skip it
    }
  }
  return best?.id ?? null;
}

function normalizeBody(value: unknown): string {
  return typeof value === "string" ? value.replace(/\r\n?/g, "\n").trim() : "";
}

function messagingLog(text: string): void {
  postMessaging({ source: HOOK_MESSAGING_SOURCE, type: "messaging-log", text });
}

function postMessaging(message: HookToAgentMessaging): void {
  try {
    window.postMessage(message, location.origin);
  } catch {
    // nothing to tell
  }
}

// =============================================================================
// --- incoming calls (calling stations only) ----------------------------------
// =============================================================================
//
// On a calling station a lead who calls the number back is answered by the AI
// agent. This notices the call ringing and tells wa-agent (which keeps it for
// the call worker); it never answers by itself — Accept is pressed only when
// wa-agent asks (accept-call), after AgentSDR chose to answer and the tab was
// armed. Started with messaging, so only in station mode: a rep's own
// WhatsApp Web is never watched.
//
// Two sources: WhatsApp's call store (WAWebCallCollection, as whatsapp-web.js
// reads it: an "add" per call, with peerJid, isVideo, isGroup, offerTime in
// seconds, and outgoing / isIncoming), and, should that module be missing or
// renamed, the page's incoming-call screen — offered with no number when the
// store said nothing about it within INCOMING_DOM_FALLBACK_MS.

type WaCallModel = {
  id?: unknown;
  peerJid?: WaWid | string;
  isVideo?: boolean;
  isGroup?: boolean;
  offerTime?: number;
  isIncoming?: boolean;
  outgoing?: boolean;
  attributes?: Record<string, unknown>;
  get?: (name: string) => unknown;
};
type WaCallCollection = {
  on?: (event: string, listener: (model: WaCallModel) => void) => void;
  getModelsArray?: () => WaCallModel[];
  models?: WaCallModel[];
};

/** The incoming-call screen is looked for this often. */
const INCOMING_DOM_POLL_MS = 1_000;
/** A screen the store said nothing about for this long is offered from the page. */
const INCOMING_DOM_FALLBACK_MS = 2_000;
/** Accept is looked for this long (and pressed at most ACCEPT_MAX_PRESSES times, this far apart). */
const ACCEPT_WAIT_MS = 10_000;
const ACCEPT_MAX_PRESSES = 3;
const ACCEPT_REPRESS_MS = 1_500;
const INCOMING_SEEN_MAX = 500;

const incoming = {
  started: false,
  attached: false,
  timer: 0,
  /** Call ids passed on (or skipped), oldest first. */
  seen: new Set<string>(),
  /** When the store last reported a ringing call. */
  lastStoreAt: 0,
  /** The incoming-call screen showing now: since when, and the id it was offered under (null: not offered). */
  screen: null as { appearedAt: number; offeredId: string | null; settled: boolean } | null,
  loggedButtons: false,
  loggedMissingStore: false,
  loggedShape: false,
  /**
   * The newest call-log message from someone else: WhatsApp adds one to the
   * caller's chat as the call starts ringing (2.3000.105 reported nothing in
   * its call store), so it names who is calling.
   */
  lastCallLog: null as { at: number; phone: string | null; jid: string | null } | null,
};

/** A call-log message within this long of the screen appearing is that call's. */
const CALL_LOG_MATCH_MS = 15_000;

/** Remembers who a just-added call-log message is from (the caller of a call ringing now). */
function noteCallLog(msg: WaMsg): void {
  try {
    // Any direction: only matched to an incoming-call screen showing within seconds of it.
    if (msg?.type !== "call_log") return;
    const remote = msg.id?.remote;
    const jid = widString(remote);
    if (!jid || isNonPersonalJid(jid)) return;
    const lidDigits = jid.endsWith("@lid") ? lidToPhoneDigits(remote) : null;
    incoming.lastCallLog = { at: Date.now(), jid, phone: jidToPhone(jid) ?? (lidDigits ? `+${lidDigits}` : null) };
  } catch {
    // only a hint for the page watch
  }
}

function startIncomingCalls(): void {
  if (incoming.started) return;
  incoming.started = true;
  tryAttachCalls();
  window.setInterval(watchIncomingScreen, INCOMING_DOM_POLL_MS);
}

/** WhatsApp's call collection, under whichever of its known names this version has. */
function callCollection(): { collection: WaCallCollection; via: string } | null {
  const callModule = waModule<WaCallCollection & { CallCollection?: WaCallCollection; default?: WaCallCollection }>("WAWebCallCollection");
  const candidates: [string, unknown][] = [
    ["WAWebCallCollection", callModule],
    ["WAWebCallCollection.CallCollection", callModule?.CallCollection],
    ["WAWebCallCollection.default", callModule?.default],
    ["WAWebCollections.Call", (waCollections() as { Call?: unknown } | null)?.Call],
  ];
  for (const [via, candidate] of candidates) {
    if (candidate && typeof (candidate as WaCallCollection).on === "function") return { collection: candidate as WaCallCollection, via };
  }
  return null;
}

function tryAttachCalls(): void {
  window.clearTimeout(incoming.timer);
  if (incoming.attached) return;
  try {
    const found = callCollection();
    if (found) {
      found.collection.on?.("add", onCallAdded);
      found.collection.on?.("remove", onCallRemoved);
      incoming.attached = true;
      messagingLog(`incoming calls: listening to WhatsApp's call store (${found.via})`);
      // A call already ringing when this attached.
      for (const model of modelsOf(found.collection)) onCallAdded(model);
      return;
    }
  } catch (error) {
    messagingLog(`incoming calls: could not attach yet: ${describe(error)}`);
  }
  const fast = Date.now() - messaging.enabledAt < MESSAGING_ATTACH_FAST_FOR_MS;
  if (!fast && !incoming.loggedMissingStore) {
    incoming.loggedMissingStore = true;
    messagingLog("incoming calls: WhatsApp's call store not found — watching the page's incoming-call screen only");
  }
  incoming.timer = window.setTimeout(tryAttachCalls, fast ? MESSAGING_ATTACH_POLL_MS : MESSAGING_ATTACH_SLOW_POLL_MS);
}

/** A call model's field: a property, else its attributes (Backbone-style models keep them there). */
function callField(model: WaCallModel, name: keyof WaCallModel): unknown {
  const direct = (model as Record<string, unknown>)[name];
  if (direct !== undefined) return direct;
  try {
    return model.attributes?.[name] ?? model.get?.(name);
  } catch {
    return undefined;
  }
}

function callIdOf(model: WaCallModel): string | null {
  const id = callField(model, "id");
  if (typeof id === "string" && id) return id;
  if (typeof id === "number") return String(id);
  const serialized = (id as { _serialized?: unknown } | null)?._serialized;
  return typeof serialized === "string" && serialized ? serialized : null;
}

function onCallAdded(model: WaCallModel): void {
  try {
    if (!model) return;
    const id = callIdOf(model);
    if (!id || incoming.seen.has(id)) return;
    const isIncoming = callField(model, "isIncoming");
    const outgoing = callField(model, "outgoing");
    const direction = isIncoming === true || outgoing === false ? "in" : isIncoming === false || outgoing === true ? "out" : null;
    if (!direction) {
      if (!incoming.loggedShape) {
        incoming.loggedShape = true;
        const keys = [...Object.keys(model), ...Object.keys(model.attributes ?? {})].slice(0, 40).join(", ");
        messagingLog(`incoming calls: a call in the store says neither isIncoming nor outgoing (fields: ${keys}) — left to the page watch`);
      }
      return;
    }
    remember(id);
    if (direction === "out") return;
    const offerTime = callField(model, "offerTime");
    const at = typeof offerTime === "number" && offerTime > 0 ? offerTime * 1000 : Date.now();
    if (Date.now() - at > INCOMING_CALL_MAX_AGE_MS) return; // an old call the store still holds
    const isVideo = callField(model, "isVideo") === true;
    if (callField(model, "isGroup") === true) {
      messagingLog("incoming calls: a group call is ringing — not offered");
      return;
    }
    const peer = callField(model, "peerJid") as WaWid | string | undefined;
    const jid = widString(peer);
    const lidDigits = jid?.endsWith("@lid") ? lidToPhoneDigits(peer) : null;
    const phone = jidToPhone(jid) ?? (lidDigits ? `+${lidDigits}` : null);
    incoming.lastStoreAt = Date.now();
    messagingLog(`incoming calls: a ${isVideo ? "video" : "voice"} call is ringing (caller ${jidKind(jid)}${phone ? "" : ", number unknown"})`);
    postMessaging({
      source: HOOK_MESSAGING_SOURCE,
      type: "incoming-call",
      call: { waCallId: id, phone, callerName: contactName(peer), isVideo, isGroup: false, at },
    });
  } catch (error) {
    messagingLog(`incoming calls: a call could not be read: ${describe(error)}`);
  }
}

function onCallRemoved(model: WaCallModel): void {
  try {
    const id = model ? callIdOf(model) : null;
    if (id) postMessaging({ source: HOOK_MESSAGING_SOURCE, type: "incoming-call-ended", waCallId: id });
  } catch {
    // never into WhatsApp's code
  }
}

function remember(id: string): void {
  incoming.seen.add(id);
  if (incoming.seen.size > INCOMING_SEEN_MAX) {
    const oldest = incoming.seen.values().next().value;
    if (oldest !== undefined) incoming.seen.delete(oldest);
  }
}

/** The page's incoming-call screen: logs its buttons once, and offers the call itself if the store did not. */
function watchIncomingScreen(): void {
  try {
    const found = findAcceptButton();
    if (!found) {
      const gone = incoming.screen;
      incoming.screen = null;
      if (gone?.offeredId) postMessaging({ source: HOOK_MESSAGING_SOURCE, type: "incoming-call-ended", waCallId: gone.offeredId });
      return;
    }
    if (!incoming.screen) {
      incoming.screen = { appearedAt: Date.now(), offeredId: null, settled: false };
      if (!incoming.loggedButtons) {
        incoming.loggedButtons = true;
        messagingLog(`incoming calls: the incoming-call screen shows ${found.where}; its buttons: ${found.labels}`);
      }
      return;
    }
    const screen = incoming.screen;
    if (screen.settled || Date.now() - screen.appearedAt < INCOMING_DOM_FALLBACK_MS) return;
    screen.settled = true;
    // The store reported it (around when the screen appeared): nothing to add.
    if (incoming.lastStoreAt >= screen.appearedAt - 5_000) return;
    screen.offeredId = `dom-${screen.appearedAt}`;
    // Who is calling: the call-log message WhatsApp added to their chat as it
    // started ringing, else a number written on the screen itself.
    const log = incoming.lastCallLog && Math.abs(incoming.lastCallLog.at - screen.appearedAt) <= CALL_LOG_MATCH_MS ? incoming.lastCallLog : null;
    const screenText = callScreenText(found.button);
    const phone = log?.phone ?? phoneFromScreenText(screenText);
    const source = log?.phone ? "its call-log message" : phone ? "the screen" : null;
    messagingLog(
      `incoming calls: the page shows an incoming call the store did not report — offering it ${source ? `(caller from ${source}${log?.jid ? `, ${jidKind(log.jid)}` : ""})` : `with no number${log ? ` (its call-log chat is ${jidKind(log.jid)}, not resolved to a number)` : ""}`}`,
    );
    postMessaging({
      source: HOOK_MESSAGING_SOURCE,
      type: "incoming-call",
      call: {
        waCallId: screen.offeredId,
        phone,
        callerName: log?.jid ? contactName(log.jid) : null,
        isVideo: /video/i.test(found.labels),
        isGroup: false,
        at: screen.appearedAt,
      },
    });
  } catch (error) {
    messagingLog(`incoming calls: the page watch failed: ${describe(error)}`);
  }
}

/** WhatsApp's Accept on an incoming call, in the page or its picture-in-picture window — never Decline. */
function findAcceptButton(): { button: HTMLElement; labels: string; where: string } | null {
  const documents = callDocuments();
  for (let i = 0; i < documents.length; i++) {
    const matches = Array.from(documents[i].querySelectorAll<HTMLElement>("button, [role='button']")).filter((element) => {
      const icon = element.querySelector("[data-icon]")?.getAttribute("data-icon") ?? "";
      return (
        isAcceptLabel(element.getAttribute("aria-label")) ||
        isAcceptLabel(element.textContent) ||
        (/accept|answer/i.test(icon) && !/decline|reject/i.test(icon))
      );
    });
    // The innermost: a press on a wrapper would miss the button's own handler.
    const button = matches.find((element) => !matches.some((other) => other !== element && element.contains(other)));
    if (button) return { button, labels: callButtonLabels(button), where: i === 0 ? "on the page" : "in picture-in-picture" };
  }
  return null;
}

/** The text of the call screen around `button` (the caller's name or number). */
function callScreenText(button: HTMLElement): string {
  let container: HTMLElement = button;
  for (let level = 0; level < 10 && container.parentElement; level++) {
    container = container.parentElement;
    if ((container.innerText ?? "").length > 200) break;
  }
  return container.innerText ?? container.textContent ?? "";
}

/** The labels of the buttons around `button` (its call screen), digits masked — for the log. */
function callButtonLabels(button: HTMLElement): string {
  let container: HTMLElement = button;
  for (let level = 0; level < 8 && container.parentElement; level++) {
    container = container.parentElement;
    if (container.querySelectorAll("button, [role='button']").length >= 2) break;
  }
  return describeButtons(container);
}

function describeButtons(root: ParentNode): string {
  const labels = Array.from(root.querySelectorAll<HTMLElement>("button, [role='button']"))
    .map((element) => {
      const icon = element.querySelector("[data-icon]")?.getAttribute("data-icon");
      return maskDigits((element.getAttribute("aria-label") || element.textContent?.trim() || (icon ? `icon:${icon}` : "")).slice(0, 40));
    })
    .filter(Boolean);
  return [...new Set(labels)].slice(0, 12).join(" | ");
}

/**
 * Presses Accept on the call ringing now, for the armed call `callId`, and
 * reports whether it took (the button went away). Up to ACCEPT_WAIT_MS for
 * the button to show; pressed again if a press did not take.
 */
async function acceptIncoming(callId: string): Promise<void> {
  const deadline = Date.now() + ACCEPT_WAIT_MS;
  let presses = 0;
  let lastPress = 0;
  let labels = "";
  let showing = false;
  while (Date.now() < deadline) {
    const found = findAcceptButton();
    showing = Boolean(found);
    if (!found) {
      if (presses) break; // gone after a press: accepted
    } else {
      labels = found.labels;
      if (presses < ACCEPT_MAX_PRESSES && (presses === 0 || Date.now() - lastPress >= ACCEPT_REPRESS_MS)) {
        pressLikeUser(found.button);
        presses += 1;
        lastPress = Date.now();
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  if (!labels) {
    // What call controls there are, to see why Accept was not found.
    labels = callDocuments()
      .map((doc) => describeButtons(doc.querySelector("[role='dialog']") ?? doc.body ?? doc))
      .filter(Boolean)
      .join(" || ")
      .slice(0, 400);
  }
  post({ source: HOOK_SOURCE, type: "accept-result", callId, clicked: presses > 0 && !showing, labels });
}

/** The events of a real mouse click, made in the element's own window (the page, or picture-in-picture). */
function pressLikeUser(element: HTMLElement): void {
  const view = (element.ownerDocument.defaultView ?? window) as Window & typeof globalThis;
  const rect = element.getBoundingClientRect();
  const at = {
    bubbles: true,
    cancelable: true,
    composed: true,
    view,
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
    button: 0,
  };
  const pointer = { ...at, pointerId: 1, pointerType: "mouse", isPrimary: true };
  element.dispatchEvent(new view.PointerEvent("pointerover", pointer));
  element.dispatchEvent(new view.MouseEvent("mouseover", at));
  element.dispatchEvent(new view.PointerEvent("pointerdown", { ...pointer, buttons: 1 }));
  element.dispatchEvent(new view.MouseEvent("mousedown", { ...at, buttons: 1 }));
  element.focus();
  element.dispatchEvent(new view.PointerEvent("pointerup", pointer));
  element.dispatchEvent(new view.MouseEvent("mouseup", at));
  element.dispatchEvent(new view.MouseEvent("click", { ...at, detail: 1 }));
}
