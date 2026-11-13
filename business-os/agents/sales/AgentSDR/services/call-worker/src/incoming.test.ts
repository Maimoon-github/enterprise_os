import { describe, expect, test } from "bun:test";
import type {
  StationIncomingCall,
  WorkerCall,
  WorkerIncomingCallRequest,
  WorkerIncomingCallResponse,
  WorkerStation,
} from "../../../src/lib/calls/stationContract";
import { Incoming, type IncomingDeps, type IncomingExtension } from "./incoming";
import type { ReadyWhatsApp } from "./jobs";

const NOW = 1_800_000_000_000;
const station = (id: string): WorkerStation =>
  ({ id, name: `number ${id}`, phone: "+910000000000", launcher: "cloak" }) as unknown as WorkerStation;
const ring = (waCallId: string, ageMs = 1_000): StationIncomingCall => ({
  waCallId,
  phone: "+911111111111",
  callerName: "Asha",
  isVideo: false,
  isGroup: false,
  at: NOW - ageMs,
});
const workerCall = (id: string): WorkerCall => ({
  id,
  phone: "+911111111111",
  recorderToken: "token",
  lead: null,
  brief: "brief",
  agentName: null,
  agentVoice: null,
  remoteRep: false,
});
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

type FakeExt = IncomingExtension & { rings: StationIncomingCall[]; takes: number };

function fakeExtension(supports = true): FakeExt {
  const ext: FakeExt = {
    version: supports ? "0.22.0" : "0.21.3",
    supportsIncoming: supports,
    rings: [],
    takes: 0,
    takeIncomingCalls: async () => {
      ext.takes++;
      return ext.rings.splice(0);
    },
  };
  return ext;
}

async function harness(exts: Record<string, FakeExt>, respond: (body: WorkerIncomingCallRequest) => Promise<WorkerIncomingCallResponse>) {
  const idle = new Set(Object.keys(exts));
  // One browser per number, as OpenStations keeps it: a new one means a reopened number.
  const readies = Object.fromEntries(Object.keys(exts).map((id) => [id, { browser: { id }, page: { id } } as unknown as ReadyWhatsApp]));
  const asked: { stationId: string; body: WorkerIncomingCallRequest }[] = [];
  const answered: { stationId: string; call: WorkerCall; ring: StationIncomingCall }[] = [];
  const logs: string[] = [];
  const finishers: (() => void)[] = [];
  const deps: IncomingDeps = {
    idleReady: () => [...idle].map((id) => ({ station: station(id), ready: readies[id] })),
    connect: async (ready) => exts[(ready.browser as unknown as { id: string }).id],
    ask: async (stationId, body) => {
      asked.push({ stationId, body });
      return respond(body);
    },
    answer: (s, call, r) => {
      answered.push({ stationId: s.id, call, ring: r });
      return new Promise<void>((resolve) => finishers.push(resolve));
    },
    workerId: "worker-1",
    log: (t) => logs.push(t),
    now: () => NOW,
  };
  const incoming = new Incoming(deps, { pollMs: 10 });
  // The first look starts reaching each extension; the next sees it.
  await incoming.pollOnce();
  await settle();
  return { incoming, idle, asked, answered, logs, finishCall: () => finishers.splice(0).forEach((finish) => finish()) };
}

const yes = async (): Promise<WorkerIncomingCallResponse> => ({ answer: true, call: workerCall("call-1") });

describe("Incoming", () => {
  test("answers a ring when AgentSDR says to, and runs the call", async () => {
    const a = fakeExtension();
    const h = await harness({ a }, yes);
    a.rings.push(ring("w1"));
    await h.incoming.pollOnce();
    expect(h.asked).toEqual([{ stationId: "a", body: { workerId: "worker-1", call: ring("w1") } }]);
    expect(h.answered.map((x) => [x.stationId, x.call.id, x.ring.waCallId])).toEqual([["a", "call-1", "w1"]]);
    expect(h.logs).toContain("incoming: ringing on number a");
    expect(h.logs).toContain("incoming: answering (call call-1)");
  });

  test("does not run the call in the poll: the loop goes on while it runs, without polling that number", async () => {
    const a = fakeExtension();
    const b = fakeExtension();
    const h = await harness({ a, b }, yes);
    a.rings.push(ring("w1"));
    await h.incoming.pollOnce(); // returns with the call still running
    const takesOnA = a.takes;
    b.rings.push(ring("w2"));
    await h.incoming.pollOnce();
    expect(a.takes).toBe(takesOnA);
    expect(h.answered.map((x) => x.stationId)).toEqual(["a", "b"]);
    h.finishCall();
    await settle();
    await h.incoming.pollOnce();
    expect(a.takes).toBe(takesOnA + 1);
  });

  test("ignores a stale ring and a ring already handled", async () => {
    const a = fakeExtension();
    const h = await harness({ a }, async () => ({ answer: false, reason: "unknown caller" }));
    a.rings.push(ring("old", 31_000), ring("w1"));
    await h.incoming.pollOnce();
    a.rings.push(ring("w1"));
    await h.incoming.pollOnce();
    expect(h.asked.map((x) => x.body.call.waCallId)).toEqual(["w1"]);
    expect(h.logs.some((l) => l.includes("31 s old"))).toBe(true);
  });

  test("runs nothing when AgentSDR says no", async () => {
    const a = fakeExtension();
    const h = await harness({ a }, async () => ({ answer: false, reason: "not a known lead" }));
    a.rings.push(ring("w1"));
    await h.incoming.pollOnce();
    expect(h.answered).toEqual([]);
    expect(h.logs).toContain("incoming: not answering (not a known lead)");
  });

  test("a failed post lets it ring, and the next ring is still asked", async () => {
    const a = fakeExtension();
    let fail = true;
    const h = await harness({ a }, async () => {
      if (fail) {
        fail = false;
        throw new Error("POST failed (502)");
      }
      return { answer: false, reason: "busy" };
    });
    a.rings.push(ring("w1"), ring("w2"));
    await h.incoming.pollOnce();
    expect(h.asked.map((x) => x.body.call.waCallId)).toEqual(["w1", "w2"]);
    expect(h.answered).toEqual([]);
    expect(h.logs.some((l) => l.includes("could not ask AgentSDR (POST failed (502))"))).toBe(true);
  });

  test("an extension before 0.22.0 is never asked, and that is said once", async () => {
    const a = fakeExtension(false);
    const h = await harness({ a }, yes);
    await h.incoming.pollOnce();
    await h.incoming.pollOnce();
    expect(a.takes).toBe(0);
    expect(h.logs.filter((l) => l.includes("needs 0.22.0+")).length).toBe(1);
  });

  test("stop waits for an answered call to end", async () => {
    const a = fakeExtension();
    const h = await harness({ a }, yes);
    a.rings.push(ring("w1"));
    await h.incoming.pollOnce();
    let stopped = false;
    const stopping = h.incoming.stop().then(() => (stopped = true));
    await settle();
    expect(stopped).toBe(false);
    h.finishCall();
    await stopping;
    expect(stopped).toBe(true);
  });
});
