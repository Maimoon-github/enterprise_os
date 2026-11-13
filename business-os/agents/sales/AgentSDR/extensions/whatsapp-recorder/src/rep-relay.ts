/**
 * A rep call's audio through AgentSDR's relay (contract.ts, "a rep talking
 * through a calling station"), from the station's side. wa-agent runs it:
 * the extension's isolated world, whose fetches the page's CSP does not
 * govern. They go out with web.whatsapp.com as their origin, which the
 * relay's routes allow by CORS, and carry the call's own recorder token.
 *
 *   down: one long GET whose lines (RepRelayEvent, NDJSON) carry the rep's
 *         voice — for wa-hook, which makes it WhatsApp's microphone — and
 *         their hang-up. Reopened with a short backoff whenever it drops
 *         while the call is on; unreachable for RELAY_LOST_HANGUP_MS, or
 *         refused for good (the call is over, or not this token's), the
 *         call is hung up — nobody could hear the lead.
 *   up:   the lead's side, through RelayUplink (src/lib/calls/relayUplink.ts):
 *         one long streaming POST, or — where streaming does not get
 *         through — POSTs of about REP_RELAY_CHUNK_MS, one in flight. A
 *         backlog past REP_RELAY_MAX_CHUNK_MS loses its oldest audio: after a
 *         stall the rep hears the lead now, not late. One request per chunk
 *         could not keep up (~1 s a round trip, 29 Oct 2026: 13 s of a
 *         100 s call dropped), which is why the stream exists.
 */

import { REP_RELAY_PING_MS, type RepRelayEvent } from "../../../src/lib/calls/contract";
import { RelayUplink } from "../../../src/lib/calls/relayUplink";

/** Waits between attempts to (re)open the down stream; the last repeats. */
const RECONNECT_BACKOFF_MS = [250, 500, 1_000, 2_000];
/** An attempt to open the down stream with no answer in this long is given up and retried. */
const CONNECT_TIMEOUT_MS = 5_000;
/** A down stream with no line at all (the relay pings every REP_RELAY_PING_MS) this long is taken as dead. */
const STREAM_SILENT_MS = 3 * REP_RELAY_PING_MS;
/** The down stream not open this long — from the start, or since it dropped — hangs up the call. */
const RELAY_LOST_HANGUP_MS = 15_000;
/** Answers that will not change on a retry: the call is over, or the token is not its. */
const PERMANENT_STATUSES = new Set([401, 403, 404, 410]);

// --- pure pieces (tested) --------------------------------------------------------

/**
 * The complete lines in `text` as relay events, and what is left after the
 * last newline (the start of a line still arriving). Lines that are not
 * JSON, or not an event we know, are skipped.
 */
export function parseRelayLines(text: string): { events: RepRelayEvent[]; rest: string } {
  const lines = text.split("\n");
  const rest = lines.pop() ?? "";
  const events: RepRelayEvent[] = [];
  for (const line of lines) {
    const event = parseRelayEvent(line);
    if (event) events.push(event);
  }
  return { events, rest };
}

function parseRelayEvent(line: string): RepRelayEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  let value: unknown;
  try {
    value = JSON.parse(trimmed);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object") return null;
  const event = value as { t?: unknown; pcm?: unknown; present?: unknown };
  if (event.t === "audio") return typeof event.pcm === "string" ? { t: "audio", pcm: event.pcm } : null;
  if (event.t === "peer") return typeof event.present === "boolean" ? { t: "peer", present: event.present } : null;
  if (event.t === "hangup") return { t: "hangup" };
  if (event.t === "uplink") return { t: "uplink" };
  if (event.t === "ping") return { t: "ping" };
  return null;
}

/** An audio event's PCM as bytes; an odd trailing byte (half a sample) is dropped. */
export function pcmFromBase64(data: string): ArrayBuffer {
  const binary = atob(data);
  const length = binary.length - (binary.length % 2);
  const bytes = new Uint8Array(length);
  for (let i = 0; i < length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// --- the relay -------------------------------------------------------------------

export type RepRelayOptions = {
  /** `${apiBase}/api/call-recorder/calls/${callId}/relay` */
  url: string;
  /** The call's recorder token. */
  token: string;
  /** The rep's voice: mono 16-bit PCM at REP_RELAY_SAMPLE_RATE. */
  play: (pcm: ArrayBuffer) => void;
  /** End the WhatsApp call: the rep hung up, or the relay is gone. Called at most once. */
  hangup: (why: string) => void;
  /** A step worth the call's log. */
  trace: (step: string) => void;
  /** For tests; the global fetch otherwise. */
  fetch?: Fetch;
  /** For tests: whether to try a streaming upload first (detected otherwise). */
  canStream?: boolean;
};

type Fetch = (url: string, init: RequestInit) => Promise<Response>;

export class RepRelay {
  private readonly fetch: Fetch;
  /** The lead's side up to the rep. */
  private readonly uplink: RelayUplink;
  private closed = false;
  /** The open (or opening) down stream's request, aborted by close(). */
  private attempt: AbortController | null = null;
  /** For the log, once: the first of the rep's audio. */
  private heardRep = false;

  constructor(private readonly options: RepRelayOptions) {
    this.fetch = options.fetch ?? ((url, init) => fetch(url, init));
    this.uplink = new RelayUplink({
      url: options.url,
      headers: this.headers(),
      log: options.trace,
      fetch: this.fetch,
      canStream: options.canStream,
    });
  }

  start(): void {
    void this.down();
    this.uplink.start();
  }

  /** Stops both directions; nothing more is played, sent or hung up. */
  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.attempt?.abort();
    this.attempt = null;
    this.uplink.close();
  }

  /** A block of the lead's side (mono 16-bit PCM at REP_RELAY_SAMPLE_RATE), for the rep. */
  sendLead(pcm: ArrayBuffer): void {
    if (this.closed) return;
    this.uplink.send(new Int16Array(pcm));
  }

  private headers(): Record<string, string> {
    return { Authorization: `Bearer ${this.options.token}` };
  }

  /** Keeps the down stream open while the call is on. */
  private async down(): Promise<void> {
    let failures = 0;
    let lastOpenAt = Date.now();
    while (!this.closed) {
      if (Date.now() - lastOpenAt > RELAY_LOST_HANGUP_MS) {
        return this.giveUp(`could not reach AgentSDR's relay for ${RELAY_LOST_HANGUP_MS / 1000} s`);
      }
      const outcome = await this.readStream(() => {
        failures = 0;
      });
      if (this.closed) return;
      if (outcome.kind === "hangup") return;
      if (outcome.kind === "refused") return this.giveUp(outcome.why);
      if (outcome.kind === "ended") lastOpenAt = Date.now();
      this.options.trace(`${outcome.why}; reconnecting`);
      await sleep(RECONNECT_BACKOFF_MS[Math.min(failures, RECONNECT_BACKOFF_MS.length - 1)]);
      failures += 1;
    }
  }

  /**
   * One down stream, from opening to its end. `ended`: it was open and then
   * stopped; `failed`: it never opened; `refused`: it never will.
   */
  private async readStream(
    onOpen: () => void,
  ): Promise<{ kind: "ended" | "failed" | "refused"; why: string } | { kind: "hangup" }> {
    const attempt = new AbortController();
    this.attempt = attempt;
    let watchdog = setTimeout(() => attempt.abort(), CONNECT_TIMEOUT_MS);
    const resetWatchdog = () => {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => attempt.abort(), STREAM_SILENT_MS);
    };
    let opened = false;
    try {
      const response = await this.fetch(this.options.url, { headers: this.headers(), cache: "no-store", signal: attempt.signal });
      if (!response.ok || !response.body) {
        const why = `AgentSDR's relay answered ${response.status}`;
        return { kind: PERMANENT_STATUSES.has(response.status) ? "refused" : "failed", why };
      }
      opened = true;
      onOpen();
      resetWatchdog();
      this.options.trace("connected to AgentSDR's relay");
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let pending = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        resetWatchdog();
        const { events, rest } = parseRelayLines(pending + value);
        pending = rest;
        for (const event of events) {
          if (this.closed) return { kind: "ended", why: "closed" };
          if (this.onEvent(event) === "hangup") return { kind: "hangup" };
        }
      }
      return { kind: "ended", why: "AgentSDR's relay closed the stream" };
    } catch (error) {
      const why = attempt.signal.aborted
        ? opened
          ? `nothing from AgentSDR's relay in ${STREAM_SILENT_MS / 1000} s`
          : `AgentSDR's relay did not answer in ${CONNECT_TIMEOUT_MS / 1000} s`
        : `${opened ? "the relay stream broke" : "could not reach AgentSDR's relay"}: ${describe(error)}`;
      return { kind: opened ? "ended" : "failed", why };
    } finally {
      clearTimeout(watchdog);
      if (this.attempt === attempt) this.attempt = null;
      attempt.abort();
    }
  }

  private onEvent(event: RepRelayEvent): "hangup" | null {
    switch (event.t) {
      case "audio": {
        const pcm = pcmFromBase64(event.pcm);
        if (pcm.byteLength === 0) return null;
        if (!this.heardRep) {
          this.heardRep = true;
          this.options.trace("first of the rep's audio received");
        }
        this.options.play(pcm);
        return null;
      }
      case "peer":
        this.options.trace(event.present ? "the rep's tab is connected" : "the rep's tab is not connected");
        return null;
      case "hangup":
        this.giveUp("the rep hung up");
        return "hangup";
      case "uplink":
        this.uplink.heard();
        return null;
      case "ping":
        return null;
    }
  }

  private giveUp(why: string): void {
    if (this.closed) return;
    this.close();
    this.options.hangup(why);
  }
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
