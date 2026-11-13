import "server-only";

import { Buffer } from "node:buffer";
import {
  REP_RELAY_MAX_CHUNK_MS,
  REP_RELAY_PING_MS,
  REP_RELAY_REP_GONE_MS,
  REP_RELAY_SAMPLE_RATE,
  REP_RELAY_STREAM_MAX_MS,
  type RepRelayEvent,
  type RepRelaySide,
} from "./contract";

/**
 * The audio relay for a rep talking through a calling station (contract.ts,
 * "a rep talking through a calling station"): per call, two sides — the rep's
 * tab and the station's WhatsApp Web — each with at most one down stream
 * open. What one side POSTs (a chunk at a time, or as one upload stream) goes
 * straight to the other's stream; nothing is stored, and audio for a side
 * with no stream (or a stream that has fallen behind) is dropped, never
 * queued.
 *
 * In-process memory, so it holds only while the app runs as one instance (as
 * deployed today). The hub is pure — timers are injected — so its rules are
 * tested without a server; the routes adapt it to streaming responses
 * (relayStream) and do the authorization.
 */

/** Most bytes one POST may carry: REP_RELAY_MAX_CHUNK_MS of mono 16-bit PCM. */
export const REP_RELAY_MAX_CHUNK_BYTES = (REP_RELAY_SAMPLE_RATE * 2 * REP_RELAY_MAX_CHUNK_MS) / 1000;
/** A down stream holds at most about this much audio its client has not read; past it, audio is dropped. */
const MAX_QUEUED_AUDIO_MS = 500;
/** That, as NDJSON bytes: base64 is 4/3 of the PCM, plus room for the framing and control events. */
export const REP_RELAY_MAX_QUEUED_BYTES = Math.ceil(((REP_RELAY_SAMPLE_RATE * 2 * MAX_QUEUED_AUDIO_MS) / 1000) * (4 / 3)) + 1_024;
/** Calls relayed at once, at most — a bound on memory, far above what one deployment's stations can place. */
export const MAX_REP_RELAYS = 100;
/** A call with neither side connected is forgotten after this. */
export const REP_RELAY_IDLE_MS = 60_000;
/**
 * A side's newer upload stream retires its older one after this: a sender
 * rotating streams ends the old one itself, so this only cuts one whose
 * client is gone without the server having noticed (a half-open connection).
 * Not at once, so the old stream's last audio, still on its way, arrives.
 */
export const REP_RELAY_UPLINK_GRACE_MS = 2_000;

export function encodeRelayEvent(event: RepRelayEvent): string {
  return `${JSON.stringify(event)}\n`;
}

export function relayAudioEvent(pcm: Uint8Array): RepRelayEvent {
  return { t: "audio", pcm: Buffer.from(pcm.buffer, pcm.byteOffset, pcm.byteLength).toString("base64") };
}

export function otherRelaySide(side: RepRelaySide): RepRelaySide {
  return side === "rep" ? "station" : "rep";
}

/** One open down stream, as the hub sees it. */
export type RelaySubscriber = {
  /** Bytes written that the client has not read yet. */
  queuedBytes(): number;
  write(line: string): void;
  /** Ends the stream (replaced by a newer one, or the call is over). */
  close(): void;
};

type TimerHandle = unknown;
export type RelayTimers = {
  setTimeout(fn: () => void, ms: number): TimerHandle;
  clearTimeout(handle: TimerHandle): void;
  setInterval(fn: () => void, ms: number): TimerHandle;
  clearInterval(handle: TimerHandle): void;
};

const SYSTEM_TIMERS: RelayTimers = {
  setTimeout: (fn, ms) => {
    const timer = setTimeout(fn, ms);
    // A relay timer must never keep the process alive on its own.
    timer.unref?.();
    return timer;
  },
  clearTimeout: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
  setInterval: (fn, ms) => {
    const timer = setInterval(fn, ms);
    timer.unref?.();
    return timer;
  },
  clearInterval: (handle) => clearInterval(handle as ReturnType<typeof setInterval>),
};

export class RelayFullError extends Error {
  constructor() {
    super("Too many calls are being relayed right now — try again in a minute");
    this.name = "RelayFullError";
  }
}

type Attached = {
  subscriber: RelaySubscriber;
  /** What authorized this stream (a hash of the rep's session or the station's token); a POST bearing the same skips the database. */
  credential: string;
  ping: TimerHandle;
};

/** One open upload stream. */
type Uplink = {
  side: RepRelaySide;
  /** Ends the stream's reading (replaced, or the call is over). */
  stop: () => void;
  /** It has delivered audio, and its side was told (`uplink`). */
  heard: boolean;
  /** A newer stream of the same side took over: this one is stopped when it fires. */
  retire: TimerHandle | null;
};

/** An open upload stream, as its route holds it. */
export type UplinkHandle = {
  /** Forwards a piece of its audio, like RepRelayHub.up; the first tells its side the stream works. */
  up(pcm: Uint8Array): boolean;
  /** The stream is done: forget it. */
  release(): void;
};

type Relay = {
  sides: Partial<Record<RepRelaySide, Attached>>;
  /** Open upload streams, oldest first. */
  uplinks: Uplink[];
  /** The rep's stream has been open at least once. */
  repSeen: boolean;
  /** Hung up (the rep, or their tab gone): a station that connects later is told at once. */
  hungUp: boolean;
  repGone: TimerHandle | null;
  idle: TimerHandle | null;
};

export class RepRelayHub {
  private readonly relays = new Map<string, Relay>();

  constructor(
    private readonly timers: RelayTimers = SYSTEM_TIMERS,
    private readonly maxRelays = MAX_REP_RELAYS,
  ) {}

  get size(): number {
    return this.relays.size;
  }

  /**
   * Opens `side`'s down stream; a stream it already had is closed. The new
   * stream hears at once whether the other side is there; the other side
   * hears that this one arrived. Returns the detach to run when the stream
   * goes (client gone, aborted). Throws RelayFullError.
   */
  attach(callId: string, side: RepRelaySide, subscriber: RelaySubscriber, credential: string): () => void {
    const relay = this.ensure(callId);
    const previous = relay.sides[side];
    const attached: Attached = {
      subscriber,
      credential,
      ping: this.timers.setInterval(() => send(subscriber, { t: "ping" }), REP_RELAY_PING_MS),
    };
    // Replaced first, so the old stream's close (and its detach) finds it gone and changes nothing.
    relay.sides[side] = attached;
    if (previous) {
      this.timers.clearInterval(previous.ping);
      safeClose(previous.subscriber);
    }
    this.clearTimer(relay, "idle");
    if (side === "rep") {
      relay.repSeen = true;
      this.clearTimer(relay, "repGone");
    }
    const other = relay.sides[otherRelaySide(side)];
    send(subscriber, { t: "peer", present: !!other });
    if (!previous && other) send(other.subscriber, { t: "peer", present: true });
    if (side === "station" && relay.hungUp) send(subscriber, { t: "hangup" });
    // A stream reopened while its side's upload stream works: say so again, the first telling may have been lost with the old one.
    if (newestUplink(relay, side)?.heard) send(subscriber, { t: "uplink" });
    return () => this.detach(callId, side, attached);
  }

  /**
   * Opens an upload stream for `side`; `stop` ends its reading. An older
   * stream of the same side is retired after REP_RELAY_UPLINK_GRACE_MS (a
   * newer replaces an older, as with down streams). Throws RelayFullError.
   */
  openUplink(callId: string, side: RepRelaySide, stop: () => void): UplinkHandle {
    const relay = this.ensure(callId);
    for (const older of relay.uplinks) {
      if (older.side !== side || older.retire != null) continue;
      older.retire = this.timers.setTimeout(() => {
        older.retire = null;
        older.stop();
      }, REP_RELAY_UPLINK_GRACE_MS);
    }
    const uplink: Uplink = { side, stop, heard: false, retire: null };
    relay.uplinks.push(uplink);
    return {
      up: (pcm) => {
        if (!uplink.heard && pcm.byteLength) {
          uplink.heard = true;
          const own = this.relays.get(callId)?.sides[side];
          if (own) send(own.subscriber, { t: "uplink" });
        }
        return this.up(callId, side, pcm);
      },
      release: () => {
        if (uplink.retire != null) this.timers.clearTimeout(uplink.retire);
        uplink.retire = null;
        relay.uplinks = relay.uplinks.filter((open) => open !== uplink);
      },
    };
  }

  /** Whether `side`'s open stream was authorized with this credential. */
  isAuthorized(callId: string, side: RepRelaySide, credential: string | null): boolean {
    if (!credential) return false;
    return this.relays.get(callId)?.sides[side]?.credential === credential;
  }

  /** Forwards `side`'s audio to the other side. False when dropped: nobody there, or their stream is behind. */
  up(callId: string, side: RepRelaySide, pcm: Uint8Array): boolean {
    const target = this.relays.get(callId)?.sides[otherRelaySide(side)];
    if (!target || !pcm.byteLength) return false;
    const line = encodeRelayEvent(relayAudioEvent(pcm));
    // The line is ASCII: its length is its size in bytes.
    if (target.subscriber.queuedBytes() + line.length > REP_RELAY_MAX_QUEUED_BYTES) return false;
    try {
      target.subscriber.write(line);
      return true;
    } catch {
      return false;
    }
  }

  /** The rep hung up: the station is told to end the WhatsApp call. Throws RelayFullError. */
  hangup(callId: string): void {
    const relay = this.ensure(callId);
    relay.hungUp = true;
    this.clearTimer(relay, "repGone");
    const station = relay.sides.station;
    if (station) send(station.subscriber, { t: "hangup" });
  }

  /** The call is over: both streams end and the call is forgotten. */
  end(callId: string): void {
    const relay = this.relays.get(callId);
    if (!relay) return;
    this.relays.delete(callId);
    this.clearTimer(relay, "repGone");
    this.clearTimer(relay, "idle");
    for (const attached of Object.values(relay.sides)) {
      this.timers.clearInterval(attached.ping);
      safeClose(attached.subscriber);
    }
    relay.sides = {};
    const uplinks = relay.uplinks;
    relay.uplinks = [];
    for (const uplink of uplinks) {
      if (uplink.retire != null) this.timers.clearTimeout(uplink.retire);
      uplink.retire = null;
      try {
        uplink.stop();
      } catch {
        // Its reading is already over.
      }
    }
  }

  private detach(callId: string, side: RepRelaySide, attached: Attached): void {
    const relay = this.relays.get(callId);
    // Already replaced by a newer stream, or the call was ended.
    if (!relay || relay.sides[side] !== attached) return;
    this.timers.clearInterval(attached.ping);
    delete relay.sides[side];
    const other = relay.sides[otherRelaySide(side)];
    if (other) send(other.subscriber, { t: "peer", present: false });
    // The rep's tab gone (closed, crashed, offline) and not back: end the call
    // rather than leave the lead talking to nobody.
    if (side === "rep" && relay.repSeen && !relay.hungUp) {
      this.clearTimer(relay, "repGone");
      relay.repGone = this.timers.setTimeout(() => {
        relay.repGone = null;
        if (this.relays.get(callId) === relay && !relay.sides.rep) this.hangup(callId);
      }, REP_RELAY_REP_GONE_MS);
    }
    if (!relay.sides.rep && !relay.sides.station) this.scheduleIdle(callId, relay);
  }

  private ensure(callId: string): Relay {
    const existing = this.relays.get(callId);
    if (existing) return existing;
    if (this.relays.size >= this.maxRelays) throw new RelayFullError();
    const relay: Relay = { sides: {}, uplinks: [], repSeen: false, hungUp: false, repGone: null, idle: null };
    this.relays.set(callId, relay);
    this.scheduleIdle(callId, relay);
    return relay;
  }

  private scheduleIdle(callId: string, relay: Relay): void {
    this.clearTimer(relay, "idle");
    relay.idle = this.timers.setTimeout(() => {
      relay.idle = null;
      if (this.relays.get(callId) === relay && !relay.sides.rep && !relay.sides.station) this.end(callId);
    }, REP_RELAY_IDLE_MS);
  }

  private clearTimer(relay: Relay, which: "idle" | "repGone"): void {
    const handle = relay[which];
    if (handle != null) this.timers.clearTimeout(handle);
    relay[which] = null;
  }
}

function newestUplink(relay: Relay, side: RepRelaySide): Uplink | undefined {
  for (let i = relay.uplinks.length - 1; i >= 0; i--) if (relay.uplinks[i]!.side === side) return relay.uplinks[i];
  return undefined;
}

function send(subscriber: RelaySubscriber, event: RepRelayEvent): void {
  try {
    subscriber.write(encodeRelayEvent(event));
  } catch {
    // The stream is going; its detach follows.
  }
}

function safeClose(subscriber: RelaySubscriber): void {
  try {
    subscriber.close();
  } catch {
    // Already closed.
  }
}

// --- the process's hub ------------------------------------------------------------

const HUB_KEY = Symbol.for("agentsdr.repRelayHub");

/** The one hub of this process — on globalThis, so every route bundle (and a dev reload) shares it. */
export function repRelay(): RepRelayHub {
  const holder = globalThis as typeof globalThis & { [HUB_KEY]?: RepRelayHub };
  return (holder[HUB_KEY] ??= new RepRelayHub());
}

/** A call is over: close its relay, if it had one. */
export function endRelay(callId: string): void {
  repRelay().end(callId);
}

// --- streaming responses -----------------------------------------------------------

const encoder = new TextEncoder();

/**
 * A down stream as a ReadableStream of NDJSON lines: attached to the hub at
 * once, detached when the client goes (`signal`, or the response is
 * cancelled). Its queue counts bytes, so the hub sees how far behind the
 * client is.
 */
export function relayStream(
  attach: (subscriber: RelaySubscriber) => () => void,
  signal: AbortSignal,
): ReadableStream<Uint8Array> {
  let closed = false;
  let detach: (() => void) | null = null;
  const stop = () => {
    if (closed) return false;
    closed = true;
    detach?.();
    return true;
  };
  return new ReadableStream<Uint8Array>(
    {
      start(controller) {
        const subscriber: RelaySubscriber = {
          queuedBytes: () => REP_RELAY_MAX_QUEUED_BYTES - (controller.desiredSize ?? 0),
          write: (line) => {
            if (!closed) controller.enqueue(encoder.encode(line));
          },
          close: () => {
            if (!stop()) return;
            try {
              controller.close();
            } catch {
              // Already cancelled.
            }
          },
        };
        detach = attach(subscriber);
        if (signal.aborted) subscriber.close();
        else signal.addEventListener("abort", () => subscriber.close(), { once: true });
      },
      cancel() {
        stop();
      },
    },
    new ByteLengthQueuingStrategy({ highWaterMark: REP_RELAY_MAX_QUEUED_BYTES }),
  );
}

/** The headers of a down stream: nothing in between may buffer or compress it. */
export const RELAY_STREAM_HEADERS = {
  "Content-Type": "application/x-ndjson",
  "Cache-Control": "no-cache, no-transform",
  "X-Accel-Buffering": "no",
} as const;

// --- upload streams ----------------------------------------------------------------

/**
 * Cuts an upload stream's bytes into pieces the relay forwards: whole
 * samples only (an odd trailing byte waits for the next chunk), each at most
 * REP_RELAY_MAX_CHUNK_BYTES.
 */
export class PcmStreamSplitter {
  private carry: number | null = null;

  constructor(private readonly maxBytes = REP_RELAY_MAX_CHUNK_BYTES) {}

  push(chunk: Uint8Array): Uint8Array[] {
    let bytes = chunk;
    if (this.carry != null && chunk.byteLength) {
      bytes = new Uint8Array(chunk.byteLength + 1);
      bytes[0] = this.carry;
      bytes.set(chunk, 1);
      this.carry = null;
    }
    const whole = bytes.byteLength - (bytes.byteLength % 2);
    if (whole < bytes.byteLength) this.carry = bytes[whole]!;
    const pieces: Uint8Array[] = [];
    for (let offset = 0; offset < whole; offset += this.maxBytes) {
      pieces.push(bytes.subarray(offset, Math.min(whole, offset + this.maxBytes)));
    }
    return pieces;
  }
}

/**
 * How an upload stream's reading ended: `ended` — the client ended the body;
 * `stopped` — the relay stopped it (replaced, the call is over, or
 * REP_RELAY_STREAM_MAX_MS); `aborted` — the client went (`signal`);
 * `broken` — the body failed.
 */
export type UploadStreamEnd = "ended" | "stopped" | "aborted" | "broken";

/**
 * Reads one side's upload stream into the relay as it arrives — never the
 * whole body first — until it ends one of the ways above. Pure but for the
 * hub and the timers, so it is tested with a constructed stream.
 */
export async function receiveUploadStream(
  hub: RepRelayHub,
  callId: string,
  side: RepRelaySide,
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  timers: RelayTimers = SYSTEM_TIMERS,
): Promise<UploadStreamEnd> {
  const reader = body.getReader();
  let end: UploadStreamEnd | null = null;
  const finish = (why: UploadStreamEnd) => {
    if (end) return;
    end = why;
    // A pending read() then resolves as done.
    void reader.cancel().catch(() => {});
  };
  const onAbort = () => finish("aborted");
  let handle: UplinkHandle;
  try {
    handle = hub.openUplink(callId, side, () => finish("stopped"));
  } catch (error) {
    void reader.cancel().catch(() => {});
    throw error;
  }
  const limit = timers.setTimeout(() => finish("stopped"), REP_RELAY_STREAM_MAX_MS);
  if (signal.aborted) onAbort();
  else signal.addEventListener("abort", onAbort, { once: true });
  const splitter = new PcmStreamSplitter();
  try {
    while (!end) {
      let result: Awaited<ReturnType<typeof reader.read>>;
      try {
        result = await reader.read();
      } catch {
        finish(signal.aborted ? "aborted" : "broken");
        break;
      }
      if (result.done) {
        finish("ended");
        break;
      }
      if (end) break;
      for (const pcm of splitter.push(result.value)) handle.up(pcm);
    }
  } finally {
    timers.clearTimeout(limit);
    signal.removeEventListener("abort", onAbort);
    handle.release();
  }
  return end ?? "ended";
}
