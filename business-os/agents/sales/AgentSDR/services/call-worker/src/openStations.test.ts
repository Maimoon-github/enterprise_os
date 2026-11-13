import { describe, expect, test } from "bun:test";
import type { WorkerLeaseResponse, WorkerStation } from "../../../src/lib/calls/stationContract";
import type { ReadyWhatsApp } from "./jobs";
import { OpenStations, type OpenStationsDeps } from "./openStations";

const station = (id: string): WorkerStation =>
  ({ id, name: `number ${id}`, phone: "+910000000000", launcher: "gologin_sdk" }) as unknown as WorkerStation;
const ready = (id: string) => ({ browser: { id }, page: { id } }) as unknown as ReadyWhatsApp;

/** A fake AgentSDR and fake browsers, recording what the manager did. */
function harness(options: { openFails?: number; messageWaitMs?: number } = {}) {
  let now = 1_000;
  let failsLeft = options.openFails ?? 0;
  const events: string[] = [];
  const grants: WorkerStation[] = [];
  const releases: string[] = [];
  const health = new Map<string, "ok" | "logged_out" | "gone">();
  const leaseCalls: { held: string[]; capacity: number }[] = [];
  const deps: OpenStationsDeps = {
    lease: async (held, capacity) => {
      leaseCalls.push({ held, capacity });
      const response: WorkerLeaseResponse = { granted: grants.splice(0), release: releases.splice(0) };
      return response;
    },
    open: async (s) => {
      events.push(`open ${s.id}`);
      if (failsLeft > 0) {
        failsLeft -= 1;
        return { error: "did not load" };
      }
      return ready(s.id);
    },
    close: async (_r, s) => void events.push(`close ${s.id}`),
    health: async (_r, s) => health.get(s.id) ?? "ok",
    log: () => {},
    now: () => now,
  };
  const manager = new OpenStations(3, deps, 10_000, options.messageWaitMs ?? 1_000);
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  return {
    manager,
    events,
    leaseCalls,
    health,
    grant: (id: string) => grants.push(station(id)),
    release: (id: string) => releases.push(id),
    advance: (ms: number) => (now += ms),
    async tick() {
      await manager.tick();
      await settle();
      await settle();
    },
  };
}

describe("OpenStations", () => {
  test("opens what it is granted, holds it, and hands it to a call", async () => {
    const h = harness();
    h.grant("a");
    await h.tick();
    expect(h.events).toEqual(["open a"]);
    expect(h.manager.state("a")).toBe("ready");
    expect(await h.manager.acquire("a")).toEqual(ready("a"));
    await h.manager.done("a");
    await h.tick();
    expect(h.leaseCalls.at(-1)).toEqual({ held: ["a"], capacity: 3 });
  });

  test("a number let go during a call is closed only after the call", async () => {
    const h = harness();
    h.grant("a");
    await h.tick();
    await h.manager.acquire("a");
    h.release("a");
    await h.tick();
    expect(h.events).toEqual(["open a"]);
    await h.manager.done("a");
    expect(h.events).toEqual(["open a", "close a"]);
    expect(h.manager.held()).toEqual([]);
  });

  test("an opening that fails is retried later, and a call meanwhile gets null", async () => {
    const h = harness({ openFails: 1 });
    h.grant("a");
    await h.tick();
    expect(h.manager.state("a")).toBe("failed");
    expect(await h.manager.acquire("a")).toBeNull();
    await h.manager.done("a");
    await h.tick();
    expect(h.events).toEqual(["open a", "open a"]);
    expect(h.manager.state("a")).toBe("ready");
  });

  test("checks: logged out is let go, gone is reopened, and it restarts after the recycle time", async () => {
    const h = harness();
    h.grant("a");
    h.grant("b");
    await h.tick();
    h.health.set("a", "logged_out");
    h.health.set("b", "gone");
    await h.tick();
    expect(h.events).toEqual(["open a", "open b", "close a", "close b", "open b"]);
    expect(h.manager.held()).toEqual(["b"]);
    h.health.set("b", "ok");
    h.advance(10_000);
    await h.tick();
    expect(h.events.slice(-2)).toEqual(["close b", "open b"]);
  });

  test("a number in a call is never checked, reopened or recycled", async () => {
    const h = harness();
    h.grant("a");
    await h.tick();
    await h.manager.acquire("a");
    h.health.set("a", "gone");
    h.advance(20_000);
    await h.tick();
    expect(h.events).toEqual(["open a"]);
  });

  test("closing for a link, and shutting down, close the browsers and give the leases back", async () => {
    const h = harness();
    h.grant("a");
    h.grant("b");
    await h.tick();
    await h.manager.closeFor("a");
    expect(h.manager.held()).toEqual(["b"]);
    await h.manager.shutdown();
    expect(h.events).toEqual(["open a", "open b", "close a", "close b"]);
    expect(h.leaseCalls.at(-1)).toEqual({ held: [], capacity: 0 });
  });

  test("shutdown waits for a close already under way (its profile save)", async () => {
    const h = harness();
    h.grant("a");
    await h.tick();
    let finishClose = () => {};
    const slowClose = new Promise<void>((resolve) => (finishClose = resolve));
    const original = (h.manager as unknown as { deps: OpenStationsDeps }).deps.close;
    (h.manager as unknown as { deps: OpenStationsDeps }).deps.close = async (r, s) => {
      await original(r, s);
      await slowClose;
    };
    h.release("a");
    void h.manager.tick();
    await new Promise((resolve) => setTimeout(resolve, 0));
    let shutDown = false;
    const stopping = h.manager.shutdown().then(() => (shutDown = true));
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(shutDown).toBe(false);
    finishClose();
    await stopping;
    expect(shutDown).toBe(true);
  });

  test("a message takes only a ready, unused number, and holds it against checks and other messages", async () => {
    const h = harness();
    h.grant("a");
    h.grant("b");
    await h.tick();
    expect(h.manager.idleReady().map((r) => r.station.id)).toEqual(["a", "b"]);
    const hold = h.manager.acquireIdle("a");
    expect(hold?.ready).toEqual(ready("a"));
    expect(h.manager.acquireIdle("a")).toBeNull();
    expect(h.manager.idleReady().map((r) => r.station.id)).toEqual(["b"]);
    h.health.set("a", "gone");
    h.advance(20_000);
    await h.tick();
    expect(h.events.filter((e) => e.endsWith(" a"))).toEqual(["open a"]);
    await hold!.done();
    await hold!.done(); // twice is harmless
    expect(h.manager.idleReady().map((r) => r.station.id)).toContain("a");
  });

  test("a number in a call is not given to a message, and a message ending does not clear the call", async () => {
    const h = harness();
    h.grant("a");
    await h.tick();
    await h.manager.acquire("a");
    expect(h.manager.idleReady()).toEqual([]);
    expect(h.manager.acquireIdle("a")).toBeNull();
    await h.manager.done("a");
    const hold = h.manager.acquireIdle("a")!;
    // A call arriving now waits for the message; the message ending leaves the call's hold in place.
    const call = h.manager.acquire("a");
    let got: unknown = "pending";
    void call.then((r) => (got = r));
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(got).toBe("pending");
    await hold.done();
    expect(await call).toEqual(ready("a"));
    expect(h.manager.acquireIdle("a")).toBeNull();
    h.health.set("a", "gone");
    await h.tick();
    expect(h.events).toEqual(["open a"]);
    await h.manager.done("a");
    expect(h.manager.acquireIdle("a")).not.toBeNull();
  });

  test("a call waits for a stuck message only so long, then goes ahead", async () => {
    const h = harness({ messageWaitMs: 20 });
    h.grant("a");
    await h.tick();
    h.manager.acquireIdle("a");
    const started = Date.now();
    expect(await h.manager.acquire("a")).toEqual(ready("a"));
    expect(Date.now() - started).toBeGreaterThanOrEqual(15);
  });

  test("a number let go during a message closes after it; during a call and a message, after both", async () => {
    const h = harness({ messageWaitMs: 5_000 });
    h.grant("a");
    await h.tick();
    const hold = h.manager.acquireIdle("a")!;
    h.release("a");
    await h.tick();
    expect(h.events).toEqual(["open a"]);
    expect(h.manager.idleReady()).toEqual([]);
    await hold.done();
    expect(h.events).toEqual(["open a", "close a"]);

    h.grant("b");
    await h.tick();
    const holdB = h.manager.acquireIdle("b")!;
    const call = h.manager.acquire("b");
    h.release("b");
    await h.tick();
    await holdB.done();
    await call;
    expect(h.events).toEqual(["open a", "close a", "open b"]);
    await h.manager.done("b");
    expect(h.events).toEqual(["open a", "close a", "open b", "close b"]);
  });

  test("closing for a link waits for a message on the number", async () => {
    const h = harness({ messageWaitMs: 5_000 });
    h.grant("a");
    await h.tick();
    const hold = h.manager.acquireIdle("a")!;
    const closing = h.manager.closeFor("a");
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(h.events).toEqual(["open a"]);
    await hold.done();
    await closing;
    expect(h.events).toEqual(["open a", "close a"]);
  });
});
