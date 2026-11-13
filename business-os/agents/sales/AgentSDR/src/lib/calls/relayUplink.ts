/**
 * One side's audio up to AgentSDR's relay (contract.ts, "a rep talking
 * through a calling station"), for both senders: the rep's tab
 * (src/components/calls/remoteRepCall.ts) and the station's extension
 * (extensions/whatsapp-recorder/src/rep-relay.ts, which imports this as it
 * imports the contract). Client-safe; imports only the contract and
 * relayPcm.ts.
 *
 *   streaming  ONE long POST whose body is a stream (REP_RELAY_STREAM_HEADER):
 *              each read of it takes everything queued, so audio goes as
 *              soon as the network takes it, with no round trip per chunk.
 *              The relay answers its first audio with an `uplink` event on
 *              this side's down stream (heard()). Every rotateMs a new
 *              stream starts and the old one's body ends.
 *   chunked    the fallback: one POST at a time of at least REP_RELAY_CHUNK_MS,
 *              what gathered meanwhile in the next; its round trips are
 *              logged every statsMs.
 *
 * Streaming falls back for the rest of the call when this browser cannot
 * stream a request body (Firefox), or when streams fail twice in a row
 * before any worked — refused (Chrome streams only over HTTP/2 or newer), or
 * carrying audio the relay never heard (something in between holds the body
 * back). Once one has worked, a failure (a network blip) only retries with
 * backoff. Either way the backlog is capped at REP_RELAY_MAX_CHUNK_MS, oldest
 * dropped: after a stall the other side hears now, not late.
 */

import { REP_RELAY_CHUNK_MS, REP_RELAY_SAMPLE_RATE, REP_RELAY_STREAM_HEADER, REP_RELAY_STREAM_ROTATE_MS } from "./contract";
import { PcmOutbox } from "./relayPcm";

export type RelayUplinkMode = "streaming" | "chunked";

type Fetch = (url: string, init: RequestInit) => Promise<Response>;

export type RelayUplinkTiming = {
  /** A stream's first audio not heard by the relay in this long: it is not arriving. */
  ackMs: number;
  /** A new stream replaces the open one this often. */
  rotateMs: number;
  /** Waits before retrying a failed stream, by failures in a row; the last repeats. */
  backoffMs: number[];
  /** Chunked: round trips are summed up in the log this often. */
  statsMs: number;
};

const DEFAULT_TIMING: RelayUplinkTiming = {
  ackMs: 5_000,
  rotateMs: REP_RELAY_STREAM_ROTATE_MS,
  backoffMs: [250, 500, 1_000, 2_000],
  statsMs: 10_000,
};

/** A rotated-out stream whose answer has not come in this long is aborted. */
const ROTATED_ABORT_MS = 10_000;
/** A stream that ended this soon, even cleanly, waits before the next. */
const QUICK_END_MS = 1_000;
const CHUNK_SAMPLES = Math.round((REP_RELAY_SAMPLE_RATE * REP_RELAY_CHUNK_MS) / 1000);

export type RelayUplinkOptions = {
  /** The side's relay URL (…/relay). */
  url: string;
  /** Sent with every request: the station's Authorization; none for the rep's tab, whose cookie goes along. */
  headers?: Record<string, string>;
  /** A step worth the call's log: the mode in use, why it fell back, round trips, drops. */
  log: (step: string) => void;
  /** For tests; the global fetch otherwise. */
  fetch?: Fetch;
  /** Whether this browser can stream a request body; detected when unset. */
  canStream?: boolean;
  /** For tests. */
  timing?: Partial<RelayUplinkTiming>;
};

// --- pure pieces (tested) --------------------------------------------------------

/** Failed streams in a row, before any worked, that send the rest of the call as chunks. */
export const STREAM_FAILURES_BEFORE_FALLBACK = 2;

/** How one streaming attempt ended. */
export type StreamAttempt = {
  /** The relay said its audio arrived (`uplink`). */
  heard: boolean;
  /** Why it failed: refused, broke, or carried audio that was not heard. Null when it just ended. */
  error: string | null;
};

export type StreamState = {
  /** A stream has been heard in this call: streaming works here. */
  worked: boolean;
  /** Failed attempts in a row. */
  failures: number;
};

/**
 * After a streaming attempt: the new state, and whether to fall back to
 * chunks. A heard stream proves streaming works; before one has,
 * STREAM_FAILURES_BEFORE_FALLBACK failures in a row give up on it. An
 * attempt that ended with no error and nothing heard (rotated while the line
 * was quiet) counts neither way.
 */
export function streamDecision(state: StreamState, attempt: StreamAttempt): StreamState & { fallBack: boolean } {
  if (attempt.heard) return { worked: true, failures: 0, fallBack: false };
  if (!attempt.error) return { ...state, fallBack: false };
  const failures = state.failures + 1;
  return { worked: state.worked, failures, fallBack: !state.worked && failures >= STREAM_FAILURES_BEFORE_FALLBACK };
}

/** Round trips of the chunked POSTs, summed up once per window. */
export class RoundTrips {
  private count = 0;
  private total = 0;
  private min = Infinity;
  private max = 0;
  private since: number | null = null;

  constructor(private readonly windowMs: number) {}

  /** Records one; returns the window's summary once `windowMs` has passed since its first. */
  add(ms: number, now: number): string | null {
    this.since ??= now;
    this.count += 1;
    this.total += ms;
    this.min = Math.min(this.min, ms);
    this.max = Math.max(this.max, ms);
    if (now - this.since < this.windowMs) return null;
    const line = `POST round trips over ${Math.round((now - this.since) / 1000)} s: min ${Math.round(this.min)} / avg ${Math.round(this.total / this.count)} / max ${Math.round(this.max)} ms (${this.count} requests)`;
    this.count = 0;
    this.total = 0;
    this.min = Infinity;
    this.max = 0;
    this.since = null;
    return line;
  }
}

/**
 * Whether fetch can send a ReadableStream body (Chrome 105+). A browser that
 * cannot sends the stream's text ("[object ReadableStream]") instead, so it
 * has to be known before trying.
 */
export function canStreamRequests(): boolean {
  try {
    let duplexAccessed = false;
    const init = {
      method: "POST",
      body: new ReadableStream(),
      get duplex() {
        duplexAccessed = true;
        return "half";
      },
    };
    const hasContentType = new Request("https://relay.invalid/", init as RequestInit).headers.has("Content-Type");
    return duplexAccessed && !hasContentType;
  } catch {
    return false;
  }
}

// --- the uplink ------------------------------------------------------------------

/** One upload stream. */
type Upload = {
  abort: AbortController;
  /** Its body ends once its pending read is answered (rotated out, or closed). */
  ending: boolean;
  /** Wakes the body's pending read: audio queued, or it is ending. */
  wake: (() => void) | null;
  /** It has carried audio. */
  delivered: boolean;
  heard: boolean;
  ack: ReturnType<typeof setTimeout> | undefined;
  /** Set when the ack wait ran out, before the stream is aborted for it. */
  notHeard: string | null;
};

export class RelayUplink {
  private readonly outbox = new PcmOutbox();
  private readonly fetch: Fetch;
  private readonly timing: RelayUplinkTiming;
  private readonly trips: RoundTrips;
  private current: RelayUplinkMode;
  private closed = false;
  /** The stream audio goes into now. */
  private upload: Upload | null = null;
  private state: StreamState = { worked: false, failures: 0 };
  private announced = false;
  /** Chunked: a POST is out. */
  private sending = false;
  /** Chunked: the last POST failed (logged once until one works). */
  private failing = false;
  private droppedSamples = 0;

  constructor(private readonly options: RelayUplinkOptions) {
    this.fetch = options.fetch ?? ((url, init) => fetch(url, init));
    this.timing = { ...DEFAULT_TIMING, ...options.timing };
    this.trips = new RoundTrips(this.timing.statsMs);
    const canStream = options.canStream ?? canStreamRequests();
    this.current = canStream ? "streaming" : "chunked";
    if (!canStream) options.log("uplink: chunked (fallback: this browser cannot stream a request body)");
  }

  get mode(): RelayUplinkMode {
    return this.current;
  }

  /** Opens the first stream (streaming), so the connection is ready before the first audio. */
  start(): void {
    if (this.current === "streaming" && !this.closed) void this.streamLoop();
  }

  /** A block of audio (mono 16-bit PCM at REP_RELAY_SAMPLE_RATE). */
  send(pcm: Int16Array): void {
    if (this.closed) return;
    const dropped = this.outbox.push(pcm);
    if (dropped) {
      if (!this.droppedSamples) this.options.log("uplink: audio is backing up; dropping the oldest");
      this.droppedSamples += dropped;
    }
    if (this.current === "streaming") wake(this.upload);
    else void this.postChunks();
  }

  /** Drops what is waiting (muted, or nobody to hear it). */
  clear(): void {
    this.outbox.clear();
  }

  /** The relay's `uplink` event: the open stream's audio arrives. */
  heard(): void {
    const upload = this.upload;
    if (!upload || upload.heard) return;
    upload.heard = true;
    clearTimeout(upload.ack);
    if (!this.announced) {
      this.announced = true;
      this.options.log("uplink: streaming");
    }
  }

  /** Stops sending; what is queued is dropped. */
  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.outbox.clear();
    const upload = this.upload;
    this.upload = null;
    if (upload) {
      upload.ending = true;
      wake(upload);
      upload.abort.abort();
    }
    if (this.droppedSamples) {
      this.options.log(`uplink: dropped ${Math.round((this.droppedSamples / REP_RELAY_SAMPLE_RATE) * 1000)} ms of audio that could not go up in time`);
    }
  }

  // --- streaming ---

  private async streamLoop(): Promise<void> {
    while (!this.closed && this.current === "streaming") {
      const started = Date.now();
      const attempt = await this.streamOnce();
      if (this.closed) return;
      const next = streamDecision(this.state, attempt);
      this.state = { worked: next.worked, failures: next.failures };
      if (next.fallBack) return this.fallBack(attempt.error ?? "streaming failed");
      if (attempt.error) this.options.log(`uplink: the stream failed (${attempt.error}); opening another`);
      const { backoffMs } = this.timing;
      const wait = attempt.error
        ? backoffMs[Math.min(next.failures - 1, backoffMs.length - 1)]!
        : Date.now() - started < QUICK_END_MS
          ? backoffMs[0]!
          : 0;
      if (wait) await sleep(wait);
    }
  }

  /**
   * One upload stream, until its request ends — or until it is rotated out,
   * when the next starts at once while this one's body finishes.
   */
  private streamOnce(): Promise<StreamAttempt> {
    return new Promise((resolve) => {
      const upload: Upload = { abort: new AbortController(), ending: false, wake: null, delivered: false, heard: false, ack: undefined, notHeard: null };
      this.upload = upload;
      let settled = false;
      const settle = (error: string | null) => {
        if (settled) return;
        settled = true;
        clearTimeout(rotate);
        clearTimeout(upload.ack);
        if (this.upload === upload) this.upload = null;
        resolve({ heard: upload.heard, error });
      };
      const rotate = setTimeout(() => {
        // Still waiting to be heard: the ack wait decides.
        if (upload.delivered && !upload.heard) return;
        upload.ending = true;
        wake(upload);
        setTimeout(() => upload.abort.abort(), ROTATED_ABORT_MS);
        settle(null);
      }, this.timing.rotateMs);
      const body = new ReadableStream<Uint8Array>(
        {
          pull: (controller) => this.pull(upload, controller),
          cancel: () => {
            upload.ending = true;
            wake(upload);
          },
        },
        // Read only when the network asks: until then audio waits in the capped outbox.
        { highWaterMark: 0 },
      );
      const init = {
        method: "POST",
        headers: { ...this.options.headers, "Content-Type": "application/octet-stream", [REP_RELAY_STREAM_HEADER]: "1" },
        body,
        duplex: "half",
        signal: upload.abort.signal,
      };
      this.fetch(this.options.url, init as RequestInit).then(
        (response) => {
          void response.body?.cancel().catch(() => {});
          if (!response.ok) settle(`AgentSDR answered ${response.status}`);
          else settle(upload.delivered && !upload.heard ? "AgentSDR did not hear its audio" : null);
        },
        (error: unknown) => settle(upload.notHeard ?? describe(error)),
      );
    });
  }

  /** The stream's body asks for more: everything queued, or wait for it. */
  private async pull(upload: Upload, controller: ReadableStreamDefaultController<Uint8Array>): Promise<void> {
    for (;;) {
      if (upload.ending || this.closed) {
        try {
          controller.close();
        } catch {
          // Cancelled already.
        }
        return;
      }
      const bytes = this.upload === upload ? this.outbox.take() : null;
      if (bytes) {
        controller.enqueue(bytes);
        this.delivered(upload);
        return;
      }
      await new Promise<void>((resolve) => (upload.wake = resolve));
    }
  }

  private delivered(upload: Upload): void {
    if (upload.delivered) return;
    upload.delivered = true;
    if (upload.heard) return;
    upload.ack = setTimeout(() => {
      if (upload.heard) return;
      upload.notHeard = `AgentSDR did not hear its audio in ${this.timing.ackMs / 1000} s`;
      upload.abort.abort();
    }, this.timing.ackMs);
  }

  private fallBack(reason: string): void {
    this.current = "chunked";
    this.options.log(`uplink: chunked (fallback: ${reason})`);
    const upload = this.upload;
    this.upload = null;
    upload?.abort.abort();
    void this.postChunks();
  }

  // --- chunked ---

  /** POSTs what is queued, one request at a time, while there is at least a chunk of it. */
  private async postChunks(): Promise<void> {
    if (this.sending) return;
    this.sending = true;
    try {
      while (!this.closed && this.outbox.size >= CHUNK_SAMPLES) {
        const body = this.outbox.take()!;
        const started = Date.now();
        try {
          const response = await this.fetch(this.options.url, {
            method: "POST",
            headers: { ...this.options.headers, "Content-Type": "application/octet-stream" },
            body,
          });
          if (!response.ok) throw new Error(`AgentSDR answered ${response.status}`);
          const summary = this.trips.add(Date.now() - started, Date.now());
          if (summary) this.options.log(`uplink: ${summary}`);
          if (this.failing) {
            this.failing = false;
            this.options.log("uplink: sending works again");
          }
        } catch (error) {
          // Real-time audio: what did not get through is not sent again.
          if (!this.failing && !this.closed) {
            this.failing = true;
            this.options.log(`uplink: could not send audio: ${describe(error)}`);
          }
        }
      }
    } finally {
      this.sending = false;
    }
  }
}

function wake(upload: Upload | null): void {
  const resolve = upload?.wake;
  if (!upload || !resolve) return;
  upload.wake = null;
  resolve();
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
