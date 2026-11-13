import { describe, expect, test } from "bun:test";
import {
  REP_RELAY_MAX_CHUNK_MS,
  REP_RELAY_PING_MS,
  REP_RELAY_REP_GONE_MS,
  REP_RELAY_SAMPLE_RATE,
  REP_RELAY_STREAM_MAX_MS,
  type RepRelayEvent,
} from "./contract";
import {
  encodeRelayEvent,
  PcmStreamSplitter,
  receiveUploadStream,
  RelayFullError,
  REP_RELAY_IDLE_MS,
  REP_RELAY_MAX_CHUNK_BYTES,
  REP_RELAY_MAX_QUEUED_BYTES,
  REP_RELAY_UPLINK_GRACE_MS,
  RepRelayHub,
  relayAudioEvent,
  relayStream,
  type RelaySubscriber,
  type RelayTimers,
} from "./repRelay.server";

/** Timers that run only when the test advances the clock. */
class FakeTimers implements RelayTimers {
  now = 0;
  private next = 1;
  private readonly pending = new Map<number, { at: number; fn: () => void; every: number | null }>();

  setTimeout = (fn: () => void, ms: number) => this.add(fn, ms, null);
  setInterval = (fn: () => void, ms: number) => this.add(fn, ms, ms);
  clearTimeout = (handle: unknown) => void this.pending.delete(handle as number);
  clearInterval = (handle: unknown) => void this.pending.delete(handle as number);

  get count(): number {
    return this.pending.size;
  }

  advance(ms: number): void {
    const until = this.now + ms;
    for (;;) {
      const due = [...this.pending.entries()].filter(([, timer]) => timer.at <= until).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      const [id, timer] = due;
      this.now = timer.at;
      if (timer.every == null) this.pending.delete(id);
      else timer.at += timer.every;
      timer.fn();
    }
    this.now = until;
  }

  private add(fn: () => void, ms: number, every: number | null): number {
    const id = this.next++;
    this.pending.set(id, { at: this.now + ms, fn, every });
    return id;
  }
}

class FakeSubscriber implements RelaySubscriber {
  events: RepRelayEvent[] = [];
  closed = false;
  backlog = 0;
  queuedBytes = () => this.backlog;
  write = (line: string) => {
    if (this.closed) throw new Error("closed");
    expect(line.endsWith("\n")).toBe(true);
    this.events.push(JSON.parse(line) as RepRelayEvent);
  };
  close = () => {
    this.closed = true;
  };
  kinds(): string[] {
    return this.events.map((event) => (event.t === "peer" ? `peer:${event.present}` : event.t));
  }
}

const CALL = "11111111-1111-1111-1111-111111111111";

function setup(maxRelays?: number) {
  const timers = new FakeTimers();
  return { timers, hub: new RepRelayHub(timers, maxRelays) };
}

describe("framing", () => {
  test("one JSON event per line; audio is base64 of the PCM", () => {
    expect(encodeRelayEvent({ t: "ping" })).toBe('{"t":"ping"}\n');
    const pcm = new Uint8Array([0x01, 0x00, 0xff, 0x7f]);
    expect(relayAudioEvent(pcm)).toEqual({ t: "audio", pcm: "AQD/fw==" });
    // A view into a larger buffer encodes only its own bytes.
    expect(relayAudioEvent(new Uint8Array([9, 9, 1, 0, 9]).subarray(2, 4))).toEqual({ t: "audio", pcm: "AQA=" });
  });

  test("limits follow the contract", () => {
    expect(REP_RELAY_MAX_CHUNK_BYTES).toBe((REP_RELAY_SAMPLE_RATE * 2 * REP_RELAY_MAX_CHUNK_MS) / 1000);
    // About half a second of audio as base64 lines.
    expect(REP_RELAY_MAX_QUEUED_BYTES).toBeGreaterThan(REP_RELAY_SAMPLE_RATE * 2 * 0.5 * (4 / 3));
    expect(REP_RELAY_MAX_QUEUED_BYTES).toBeLessThan(REP_RELAY_SAMPLE_RATE * 2 * 0.6 * (4 / 3));
  });
});

describe("RepRelayHub", () => {
  test("audio goes to the other side only, and is dropped with nobody there", () => {
    const { hub } = setup();
    const rep = new FakeSubscriber();
    hub.attach(CALL, "rep", rep, "rep-cred");
    expect(hub.up(CALL, "rep", new Uint8Array(4))).toBe(false);
    const station = new FakeSubscriber();
    hub.attach(CALL, "station", station, "station-cred");
    expect(hub.up(CALL, "rep", new Uint8Array([1, 0]))).toBe(true);
    expect(hub.up(CALL, "station", new Uint8Array([2, 0]))).toBe(true);
    expect(station.events.filter((event) => event.t === "audio")).toEqual([{ t: "audio", pcm: "AQA=" }]);
    expect(rep.events.filter((event) => event.t === "audio")).toEqual([{ t: "audio", pcm: "AgA=" }]);
    expect(hub.up("22222222-2222-2222-2222-222222222222", "rep", new Uint8Array(2))).toBe(false);
  });

  test("never queues more than about half a second for a side that is behind", () => {
    const { hub } = setup();
    const station = new FakeSubscriber();
    hub.attach(CALL, "rep", new FakeSubscriber(), "r");
    hub.attach(CALL, "station", station, "s");
    station.backlog = REP_RELAY_MAX_QUEUED_BYTES - 100;
    expect(hub.up(CALL, "rep", new Uint8Array(1_280))).toBe(false);
    station.backlog = 0;
    expect(hub.up(CALL, "rep", new Uint8Array(1_280))).toBe(true);
  });

  test("presence: each side hears the other arrive and leave, and a new stream hears where things stand", () => {
    const { hub } = setup();
    const rep = new FakeSubscriber();
    hub.attach(CALL, "rep", rep, "r");
    expect(rep.kinds()).toEqual(["peer:false"]);
    const station = new FakeSubscriber();
    const detachStation = hub.attach(CALL, "station", station, "s");
    expect(station.kinds()).toEqual(["peer:true"]);
    expect(rep.kinds()).toEqual(["peer:false", "peer:true"]);
    detachStation();
    expect(rep.kinds()).toEqual(["peer:false", "peer:true", "peer:false"]);
  });

  test("a new stream replaces the old one, which is closed, without the other side seeing a gap", () => {
    const { hub } = setup();
    const station = new FakeSubscriber();
    hub.attach(CALL, "station", station, "s");
    const first = new FakeSubscriber();
    // Closing a real stream runs its detach, as relayStream's does.
    const detachFirst = hub.attach(CALL, "rep", first, "r");
    first.close = () => {
      first.closed = true;
      detachFirst();
    };
    const second = new FakeSubscriber();
    hub.attach(CALL, "rep", second, "r2");
    expect(first.closed).toBe(true);
    expect(station.kinds()).toEqual(["peer:false", "peer:true"]);
    // The replaced stream's own detach changes nothing.
    detachFirst();
    expect(station.kinds()).toEqual(["peer:false", "peer:true"]);
    hub.up(CALL, "station", new Uint8Array(2));
    expect(second.kinds()).toContain("audio");
    expect(hub.isAuthorized(CALL, "rep", "r")).toBe(false);
    expect(hub.isAuthorized(CALL, "rep", "r2")).toBe(true);
  });

  test("authorization holds only while that side's stream is open with that credential", () => {
    const { hub } = setup();
    expect(hub.isAuthorized(CALL, "station", "s")).toBe(false);
    const detach = hub.attach(CALL, "station", new FakeSubscriber(), "s");
    expect(hub.isAuthorized(CALL, "station", "s")).toBe(true);
    expect(hub.isAuthorized(CALL, "station", null)).toBe(false);
    expect(hub.isAuthorized(CALL, "rep", "s")).toBe(false);
    detach();
    expect(hub.isAuthorized(CALL, "station", "s")).toBe(false);
  });

  test("hang-up reaches the station, now or as soon as it connects", () => {
    const { hub } = setup();
    const station = new FakeSubscriber();
    hub.attach(CALL, "station", station, "s");
    hub.hangup(CALL);
    expect(station.kinds()).toContain("hangup");

    const other = "33333333-3333-3333-3333-333333333333";
    hub.hangup(other);
    const late = new FakeSubscriber();
    hub.attach(other, "station", late, "s");
    expect(late.kinds()).toEqual(["peer:false", "hangup"]);
  });

  test("the rep's tab gone for REP_RELAY_REP_GONE_MS hangs up; back in time, it does not", () => {
    const { hub, timers } = setup();
    const station = new FakeSubscriber();
    hub.attach(CALL, "station", station, "s");
    let detachRep = hub.attach(CALL, "rep", new FakeSubscriber(), "r");
    detachRep();
    timers.advance(REP_RELAY_REP_GONE_MS - 1_000);
    detachRep = hub.attach(CALL, "rep", new FakeSubscriber(), "r");
    timers.advance(REP_RELAY_REP_GONE_MS * 2);
    expect(station.kinds()).not.toContain("hangup");
    detachRep();
    timers.advance(REP_RELAY_REP_GONE_MS);
    expect(station.kinds()).toContain("hangup");
  });

  test("no rep-gone hang-up before the rep ever connected", () => {
    const { hub, timers } = setup();
    const station = new FakeSubscriber();
    hub.attach(CALL, "station", station, "s");
    timers.advance(REP_RELAY_REP_GONE_MS * 3);
    expect(station.kinds()).not.toContain("hangup");
  });

  test("pings every open stream, and stops when it goes", () => {
    const { hub, timers } = setup();
    const rep = new FakeSubscriber();
    const detach = hub.attach(CALL, "rep", rep, "r");
    timers.advance(REP_RELAY_PING_MS * 3);
    expect(rep.kinds().filter((kind) => kind === "ping")).toHaveLength(3);
    detach();
    timers.advance(REP_RELAY_PING_MS * 3);
    expect(rep.kinds().filter((kind) => kind === "ping")).toHaveLength(3);
  });

  test("a call with nobody connected is forgotten after a while; end() closes both streams at once", () => {
    const { hub, timers } = setup();
    const detach = hub.attach(CALL, "rep", new FakeSubscriber(), "r");
    detach();
    expect(hub.size).toBe(1);
    timers.advance(REP_RELAY_IDLE_MS);
    expect(hub.size).toBe(0);
    expect(timers.count).toBe(0);

    const rep = new FakeSubscriber();
    const station = new FakeSubscriber();
    hub.attach(CALL, "rep", rep, "r");
    hub.attach(CALL, "station", station, "s");
    hub.end(CALL);
    expect(rep.closed && station.closed).toBe(true);
    expect(hub.size).toBe(0);
    expect(timers.count).toBe(0);
  });

  test("refuses a new call past the cap, but keeps serving the ones it has", () => {
    const { hub } = setup(1);
    hub.attach(CALL, "rep", new FakeSubscriber(), "r");
    expect(() => hub.attach("44444444-4444-4444-4444-444444444444", "rep", new FakeSubscriber(), "r")).toThrow(RelayFullError);
    expect(() => hub.attach(CALL, "station", new FakeSubscriber(), "s")).not.toThrow();
  });
});

describe("relayStream", () => {
  test("streams NDJSON lines and detaches when the client cancels", async () => {
    const { hub } = setup();
    const abort = new AbortController();
    const body = relayStream((subscriber) => hub.attach(CALL, "rep", subscriber, "r"), abort.signal);
    const station = new FakeSubscriber();
    hub.attach(CALL, "station", station, "s");
    hub.up(CALL, "station", new Uint8Array([1, 0]));
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let text = "";
    while (text.split("\n").length < 4) text += decoder.decode((await reader.read()).value, { stream: true });
    expect(text.split("\n").filter(Boolean).map((line) => JSON.parse(line))).toEqual([
      { t: "peer", present: false },
      { t: "peer", present: true },
      { t: "audio", pcm: "AQA=" },
    ]);
    await reader.cancel();
    expect(hub.isAuthorized(CALL, "rep", "r")).toBe(false);
    expect(station.kinds()).toEqual(["peer:true", "peer:false"]);
  });

  test("an aborted request closes the stream and detaches", async () => {
    const { hub } = setup();
    const abort = new AbortController();
    const body = relayStream((subscriber) => hub.attach(CALL, "rep", subscriber, "r"), abort.signal);
    abort.abort();
    expect(hub.isAuthorized(CALL, "rep", "r")).toBe(false);
    const reader = body.getReader();
    // The first event was queued before the abort; then the stream is done.
    expect((await reader.read()).done).toBe(false);
    expect((await reader.read()).done).toBe(true);
  });

  test("the hub sees the client's backlog", () => {
    const { hub } = setup();
    hub.attach(CALL, "station", new FakeSubscriber(), "s");
    relayStream((subscriber) => hub.attach(CALL, "rep", subscriber, "r"), new AbortController().signal);
    // Nobody reads this stream: it fills to about half a second, then drops.
    let delivered = 0;
    for (let i = 0; i < 100; i++) if (hub.up(CALL, "station", new Uint8Array(1_280))) delivered++;
    const lineBytes = encodeRelayEvent(relayAudioEvent(new Uint8Array(1_280))).length;
    expect(delivered).toBeGreaterThan(0);
    expect(delivered * lineBytes).toBeLessThanOrEqual(REP_RELAY_MAX_QUEUED_BYTES);
    expect(delivered).toBeLessThan(100);
  });
});

describe("PcmStreamSplitter", () => {
  test("keeps samples whole: an odd trailing byte waits for the next chunk", () => {
    const splitter = new PcmStreamSplitter();
    expect(splitter.push(new Uint8Array([1, 0, 2]))).toEqual([new Uint8Array([1, 0])]);
    expect(splitter.push(new Uint8Array([0, 3]))).toEqual([new Uint8Array([2, 0])]);
    expect(splitter.push(new Uint8Array([0]))).toEqual([new Uint8Array([3, 0])]);
    expect(splitter.push(new Uint8Array([5]))).toEqual([]);
    expect(splitter.push(new Uint8Array(0))).toEqual([]);
    expect(splitter.push(new Uint8Array([0]))).toEqual([new Uint8Array([5, 0])]);
  });

  test("splits a large chunk into pieces of at most the limit", () => {
    const splitter = new PcmStreamSplitter(4);
    const pieces = splitter.push(new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]));
    expect(pieces).toEqual([new Uint8Array([1, 2, 3, 4]), new Uint8Array([5, 6, 7, 8]), new Uint8Array([9, 10])]);
    expect(new PcmStreamSplitter().push(new Uint8Array(REP_RELAY_MAX_CHUNK_BYTES * 2 + 2)).map((piece) => piece.byteLength)).toEqual([
      REP_RELAY_MAX_CHUNK_BYTES,
      REP_RELAY_MAX_CHUNK_BYTES,
      2,
    ]);
  });
});

/** An upload body the test writes to as it goes, the way a client streams one. */
function uploadBody() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
    cancel() {
      cancelled = true;
    },
  });
  return {
    body,
    write: (bytes: number[]) => controller.enqueue(new Uint8Array(bytes)),
    end: () => controller.close(),
    fail: () => controller.error(new Error("connection reset")),
    get cancelled() {
      return cancelled;
    },
  };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const audioOf = (subscriber: FakeSubscriber) =>
  subscriber.events.flatMap((event) => (event.t === "audio" ? [Array.from(Buffer.from(event.pcm, "base64"))] : []));

describe("receiveUploadStream", () => {
  function connected() {
    const { timers, hub } = setup();
    const rep = new FakeSubscriber();
    const station = new FakeSubscriber();
    hub.attach(CALL, "rep", rep, "r");
    hub.attach(CALL, "station", station, "s");
    return { timers, hub, rep, station };
  }

  test("forwards audio as it arrives, before the body ends, with odd bytes carried over", async () => {
    const { timers, hub, rep, station } = connected();
    const upload = uploadBody();
    const done = receiveUploadStream(hub, CALL, "station", upload.body, new AbortController().signal, timers);
    upload.write([1, 0, 2]);
    await tick();
    expect(audioOf(rep)).toEqual([[1, 0]]);
    // The stream works: the station (its own side) is told, once.
    expect(station.kinds().filter((kind) => kind === "uplink")).toHaveLength(1);
    upload.write([0, 3, 0]);
    await tick();
    expect(audioOf(rep)).toEqual([[1, 0], [2, 0, 3, 0]]);
    expect(station.kinds().filter((kind) => kind === "uplink")).toHaveLength(1);
    upload.end();
    expect(await done).toBe("ended");
    // The duration limit's timer is gone with it.
    timers.advance(REP_RELAY_STREAM_MAX_MS);
    expect(rep.closed).toBe(false);
  });

  test("ends when the client goes, and when the body breaks", async () => {
    const { timers, hub } = connected();
    const aborted = uploadBody();
    const abort = new AbortController();
    const first = receiveUploadStream(hub, CALL, "rep", aborted.body, abort.signal, timers);
    aborted.write([1, 0]);
    await tick();
    abort.abort();
    expect(await first).toBe("aborted");
    expect(aborted.cancelled).toBe(true);

    const broken = uploadBody();
    const second = receiveUploadStream(hub, CALL, "rep", broken.body, new AbortController().signal, timers);
    broken.fail();
    expect(await second).toBe("broken");
  });

  test("the call's relay ending stops it", async () => {
    const { timers, hub } = connected();
    const upload = uploadBody();
    const done = receiveUploadStream(hub, CALL, "rep", upload.body, new AbortController().signal, timers);
    await tick();
    hub.end(CALL);
    expect(await done).toBe("stopped");
    expect(upload.cancelled).toBe(true);
  });

  test("is stopped after REP_RELAY_STREAM_MAX_MS", async () => {
    const { timers, hub } = connected();
    const upload = uploadBody();
    const done = receiveUploadStream(hub, CALL, "rep", upload.body, new AbortController().signal, timers);
    await tick();
    timers.advance(REP_RELAY_STREAM_MAX_MS);
    expect(await done).toBe("stopped");
  });

  test("a newer stream of the same side retires the older after a grace, which still delivers meanwhile", async () => {
    const { timers, hub, rep } = connected();
    const older = uploadBody();
    const olderDone = receiveUploadStream(hub, CALL, "station", older.body, new AbortController().signal, timers);
    const newer = uploadBody();
    const newerDone = receiveUploadStream(hub, CALL, "station", newer.body, new AbortController().signal, timers);
    older.write([1, 0]);
    newer.write([2, 0]);
    await tick();
    expect(audioOf(rep)).toEqual([[1, 0], [2, 0]]);
    timers.advance(REP_RELAY_UPLINK_GRACE_MS);
    expect(await olderDone).toBe("stopped");
    newer.write([3, 0]);
    await tick();
    expect(audioOf(rep)).toEqual([[1, 0], [2, 0], [3, 0]]);
    newer.end();
    expect(await newerDone).toBe("ended");
  });

  test("an older stream that ends on its own within the grace is not stopped", async () => {
    const { timers, hub } = connected();
    const older = uploadBody();
    const olderDone = receiveUploadStream(hub, CALL, "rep", older.body, new AbortController().signal, timers);
    const newer = uploadBody();
    void receiveUploadStream(hub, CALL, "rep", newer.body, new AbortController().signal, timers);
    await tick();
    older.end();
    expect(await olderDone).toBe("ended");
    expect(timers.count).toBeGreaterThan(0);
    timers.advance(REP_RELAY_UPLINK_GRACE_MS);
    expect(newer.cancelled).toBe(false);
  });

  test("a side's down stream that reconnects hears again that its upload stream works", async () => {
    const { timers, hub } = connected();
    const upload = uploadBody();
    void receiveUploadStream(hub, CALL, "station", upload.body, new AbortController().signal, timers);
    upload.write([1, 0]);
    await tick();
    const again = new FakeSubscriber();
    hub.attach(CALL, "station", again, "s");
    expect(again.kinds()).toContain("uplink");
    const rep = new FakeSubscriber();
    hub.attach(CALL, "rep", rep, "r");
    expect(rep.kinds()).not.toContain("uplink");
  });

  test("past the relay cap it throws RelayFullError and lets go of the body", async () => {
    const { timers, hub } = setup(0);
    const upload = uploadBody();
    await expect(receiveUploadStream(hub, CALL, "rep", upload.body, new AbortController().signal, timers)).rejects.toBeInstanceOf(RelayFullError);
    expect(upload.cancelled).toBe(true);
  });
});
