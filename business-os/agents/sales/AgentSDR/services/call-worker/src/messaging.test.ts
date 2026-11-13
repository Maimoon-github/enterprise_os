import { describe, expect, test } from "bun:test";
import type {
  StationInboundMessage,
  StationInboundTake,
  StationSendResult,
  WorkerInboundRequest,
  WorkerLeaseResponse,
  WorkerMessageJob,
  WorkerMessageResultRequest,
  WorkerStation,
} from "../../../src/lib/calls/stationContract";
import type { ReadyWhatsApp } from "./jobs";
import { InboundQueue, inboundBatches, Messaging, type MessagingDeps, type MessagingExtension } from "./messaging";
import { OpenStations, type OpenStationsDeps } from "./openStations";

const station = (id: string): WorkerStation =>
  ({ id, name: `number ${id}`, phone: "+910000000000", launcher: "cloak" }) as unknown as WorkerStation;
const msg = (n: number): StationInboundMessage => ({
  providerMessageId: `id${n}`,
  chatPhone: "+911111111111",
  chatJid: "911111111111@c.us",
  chatName: null,
  direction: "inbound",
  text: `m${n}`,
  sentAt: n,
});
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("inbound batches", () => {
  test("chunks to the batch limit and never mixes sources", () => {
    const items = [
      ...Array.from({ length: 250 }, (_, i) => ({ source: "store" as const, message: msg(i) })),
      { source: "dom" as const, message: msg(999) },
    ];
    const batches = inboundBatches(items);
    expect(batches.map((b) => [b.source, b.messages.length])).toEqual([
      ["store", 100],
      ["store", 100],
      ["store", 50],
      ["dom", 1],
    ]);
    expect(batches[1].messages[0].providerMessageId).toBe("id100");
  });

  test("the queue keeps what a failed post did not deliver, resends it first, and caps by dropping the oldest", async () => {
    const logs: string[] = [];
    const q = new InboundQueue((t) => logs.push(t), 150);
    q.add("a", "store", Array.from({ length: 160 }, (_, i) => msg(i)));
    expect(q.size("a")).toBe(150);
    expect(logs.join()).toContain("10 received message(s)");
    const posted: WorkerInboundRequest[] = [];
    let fail = 1; // the second post fails
    const post = async (b: WorkerInboundRequest) => {
      if (posted.length === 1 && fail-- > 0) throw new Error("503");
      posted.push(b);
    };
    expect(await q.flush("a", post)).toEqual({ posted: 100, error: "503" });
    expect(posted[0].messages[0].providerMessageId).toBe("id10");
    expect(q.size("a")).toBe(50);
    q.add("a", "store", [msg(500)]);
    expect(await q.flush("a", post)).toEqual({ posted: 51 });
    expect(posted[1].messages[0].providerMessageId).toBe("id110");
    expect(posted[1].messages.at(-1)?.providerMessageId).toBe("id500");
    expect(q.stations()).toEqual([]);
  });
});

type FakeExt = MessagingExtension & { sent: { phone: string; text: string }[]; inbox: StationInboundMessage[] };

function fakeExtension(options: { supports?: boolean; send?: () => Promise<StationSendResult>; source?: StationInboundTake["source"] } = {}): FakeExt {
  const ext: FakeExt = {
    version: options.supports === false ? "0.20.0" : "0.21.0",
    supportsMessaging: options.supports !== false,
    sent: [],
    inbox: [],
    sendMessage: async (req) => {
      ext.sent.push(req);
      return options.send ? options.send() : { ok: true, providerMessageId: "wamid1" };
    },
    takeInbound: async () => ({ source: options.source ?? "store", messages: ext.inbox.splice(0) }),
  };
  return ext;
}

/** Real OpenStations (fake browsers) under a Messaging with a fake AgentSDR. */
async function harness(exts: Record<string, FakeExt>) {
  const ready = (id: string) => ({ browser: { id }, page: { id } }) as unknown as ReadyWhatsApp;
  const grants = Object.keys(exts).map(station);
  const stationsDeps: OpenStationsDeps = {
    lease: async (): Promise<WorkerLeaseResponse> => ({ granted: grants.splice(0), release: [] }),
    open: async (s) => ready(s.id),
    close: async () => {},
    health: async () => "ok",
    log: () => {},
    now: () => Date.now(),
  };
  const stations = new OpenStations(3, stationsDeps, 10_000_000, 5_000);
  await stations.tick();
  await settle();
  const jobs: WorkerMessageJob[] = [];
  const claims: string[][] = [];
  const reports: { id: string; body: WorkerMessageResultRequest }[] = [];
  const inbound: { id: string; body: WorkerInboundRequest }[] = [];
  const logs: string[] = [];
  let reportFailures = 0;
  let inboundFailures = 0;
  const deps: MessagingDeps = {
    idleReady: () => stations.idleReady(),
    acquireIdle: (id) => stations.acquireIdle(id),
    claim: async (ids) => {
      claims.push(ids);
      return jobs.shift() ?? null;
    },
    report: async (id, body) => {
      if (reportFailures-- > 0) throw new Error("502");
      reports.push({ id, body });
    },
    postInbound: async (id, body) => {
      if (inboundFailures-- > 0) throw new Error("502");
      inbound.push({ id, body });
      return { stored: body.messages.length, skipped: 0 };
    },
    connect: async (r) => exts[(r.browser as unknown as { id: string }).id],
    log: (t) => logs.push(t),
    now: () => Date.now(),
    sleep: async () => {},
  };
  const messaging = new Messaging(deps, { messagePollMs: 10, inboundPollMs: 10_000, sendTimeoutMs: 30 });
  // First look starts reaching each extension; the next sees it.
  await messaging.messageOnce();
  await settle();
  return {
    stations,
    messaging,
    jobs,
    claims,
    reports,
    inbound,
    logs,
    failReports: (n: number) => (reportFailures = n),
    failInbound: (n: number) => (inboundFailures = n),
  };
}

const job = (id: string, stationId: string): WorkerMessageJob => ({ id, stationId, phone: "+912222222222", body: "hello" });

describe("Messaging", () => {
  test("offers only numbers whose extension can message, and says once that an old one cannot", async () => {
    const h = await harness({ a: fakeExtension(), b: fakeExtension({ supports: false }) });
    expect(await h.messaging.messageOnce()).toBe(false);
    await h.messaging.messageOnce();
    expect(h.claims.slice(-2)).toEqual([["a"], ["a"]]);
    expect(h.logs.filter((l) => l.includes("needs 0.21.0+")).length).toBe(1);
  });

  test("sends a claimed message, releases the number, and reports it sent", async () => {
    const a = fakeExtension();
    const h = await harness({ a });
    h.jobs.push(job("m1", "a"));
    expect(await h.messaging.messageOnce()).toBe(true);
    expect(a.sent).toEqual([{ phone: "+912222222222", text: "hello" }]);
    expect(h.reports[0].id).toBe("m1");
    expect(h.reports[0].body).toMatchObject({ ok: true, providerMessageId: "wamid1" });
    expect(h.stations.idleReady().map((r) => r.station.id)).toEqual(["a"]);
  });

  test("a job for a number that became busy goes back, retryable, without sending", async () => {
    const a = fakeExtension();
    const h = await harness({ a });
    h.jobs.push(job("m1", "a"));
    // The claim loop takes the number for a call between the offer and the send.
    const claim = (h.messaging as unknown as { deps: MessagingDeps }).deps.claim;
    (h.messaging as unknown as { deps: MessagingDeps }).deps.claim = async (ids) => {
      const j = await claim(ids);
      await h.stations.acquire("a");
      return j;
    };
    await h.messaging.messageOnce();
    expect(a.sent).toEqual([]);
    expect(h.reports[0].body).toEqual({ ok: false, retryable: true, error: "station busy" });
  });

  test("a send that hangs is reported not retryable, and the number is freed", async () => {
    const a = fakeExtension({ send: () => new Promise(() => {}) });
    const h = await harness({ a });
    h.jobs.push(job("m1", "a"));
    await h.messaging.messageOnce();
    expect(h.reports[0].body).toEqual({ ok: false, retryable: false, uncertain: true, error: "timed out — may have been sent" });
    expect(h.stations.acquireIdle("a")).not.toBeNull();
  });

  test("the extension's own refusal keeps its retryable flag; a thrown error is never retried", async () => {
    let n = 0;
    const a = fakeExtension({
      send: async () => {
        if (n++ === 0) return { ok: false, error: "WhatsApp Web not ready", retryable: true };
        throw new Error("Execution context was destroyed");
      },
    });
    const h = await harness({ a });
    h.jobs.push(job("m1", "a"), job("m2", "a"));
    await h.messaging.messageOnce();
    await h.messaging.messageOnce();
    expect(h.reports.map((r) => r.body)).toEqual([
      { ok: false, error: "WhatsApp Web not ready", retryable: true, uncertain: false },
      { ok: false, retryable: false, uncertain: true, error: "extension: Execution context was destroyed" },
    ]);
  });

  test("a failed result report is retried", async () => {
    const h = await harness({ a: fakeExtension() });
    h.failReports(2);
    h.jobs.push(job("m1", "a"));
    await h.messaging.messageOnce();
    expect(h.reports.length).toBe(1);
  });

  test("a call wanting the number waits for the send on it", async () => {
    let finish: (r: StationSendResult) => void = () => {};
    const a = fakeExtension({ send: () => new Promise((resolve) => (finish = resolve)) });
    const h = await harness({ a });
    (h.messaging as unknown as { options: { sendTimeoutMs: number } }).options.sendTimeoutMs = 5_000;
    h.jobs.push(job("m1", "a"));
    const sending = h.messaging.messageOnce();
    await settle();
    let callGot: unknown = "waiting";
    void h.stations.acquire("a").then((r) => (callGot = r));
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(callGot).toBe("waiting");
    finish({ ok: true, providerMessageId: null });
    await sending;
    await settle();
    expect(callGot).not.toBe("waiting");
  });

  test("reads received messages, posts them, keeps a failed post for next time, and logs the source once", async () => {
    const a = fakeExtension();
    const h = await harness({ a });
    a.inbox.push(msg(1), msg(2));
    h.failInbound(1);
    await h.messaging.inboundPass();
    expect(h.inbound).toEqual([]);
    expect(h.messaging.inbound.size("a")).toBe(2);
    a.inbox.push(msg(3));
    await h.messaging.inboundPass();
    expect(h.inbound.length).toBe(1);
    expect(h.inbound[0].body.messages.map((m) => m.providerMessageId)).toEqual(["id1", "id2", "id3"]);
    expect(h.logs.filter((l) => l.includes("reads received messages from")).length).toBe(1);
    expect(h.stations.idleReady().length).toBe(1);
  });

  test("a number in a call is not read; the read after the call picks it up", async () => {
    const a = fakeExtension();
    const h = await harness({ a });
    a.inbox.push(msg(1));
    await h.stations.acquire("a");
    await h.messaging.inboundPass(new Set(["a"]));
    expect(h.inbound).toEqual([]);
    await h.stations.done("a");
    await h.messaging.inboundPass(new Set(["a"]));
    expect(h.inbound.length).toBe(1);
  });

  test("stop finishes the loop and posts once more", async () => {
    const a = fakeExtension();
    const h = await harness({ a });
    h.messaging.start();
    await new Promise((resolve) => setTimeout(resolve, 20));
    a.inbox.push(msg(7));
    await h.messaging.stop();
    expect(h.inbound.at(-1)?.body.messages[0].providerMessageId).toBe("id7");
  });
});
