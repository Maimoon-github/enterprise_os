import type { WorkerLeaseResponse, WorkerStation } from "../../../src/lib/calls/stationContract";
import type { ReadyWhatsApp } from "./jobs";

/**
 * Keeps numbers' WhatsApp Web open between calls (KEEP_OPEN numbers at most).
 *
 * Opening a browser for every call cost ~13 s before dialing — GoLogin's start,
 * WhatsApp Web loading the chats — and sometimes failed outright (27 Oct 2026).
 * Held open, a call only opens the chat and dials. Each number is leased from
 * AgentSDR (POST /api/call-worker/leases, renewed every 20 s): while this
 * worker holds it, no other worker opens its profile or runs its calls.
 *
 * Every tick: renew the leases and take new ones up to capacity; close the
 * numbers AgentSDR no longer wants open (paused, logged out, being relinked);
 * check the open ones (closed or crashed → reopened; logged out → reported and
 * let go); reopen each after RECYCLE_MS, which also saves its profile and keeps
 * a long-running page's memory in check. A number in use is left alone.
 *
 * Two things use an open number: a call (acquire/done, from the claim loop)
 * and a message send or inbound read (acquireIdle, from src/messaging.ts).
 * They hold separate flags, so neither clears the other's. A message only
 * takes a number that is ready and unused; a call always takes it, but first
 * waits (up to MESSAGE_WAIT_MS) for a message already on it to finish, so the
 * two never drive the same page at once.
 */

export type OpenStationsDeps = {
  lease(held: string[], capacity: number): Promise<WorkerLeaseResponse>;
  /** Opens the number's browser and WhatsApp Web, checked ready to call (or why not — the browser is then closed). */
  open(station: WorkerStation): Promise<ReadyWhatsApp | { error: string }>;
  /** Closes it, saving the profile. */
  close(ready: ReadyWhatsApp, station: WorkerStation): Promise<void>;
  /** "logged_out" is reported to AgentSDR by the check itself. */
  health(ready: ReadyWhatsApp, station: WorkerStation): Promise<"ok" | "logged_out" | "gone">;
  log(text: string): void;
  now(): number;
};

type Slot = {
  station: WorkerStation;
  state: "opening" | "ready" | "failed" | "closing";
  ready: ReadyWhatsApp | null;
  opening: Promise<void> | null;
  openedAt: number;
  failures: number;
  retryAt: number;
  /** A call is using it (open or not): no check, reopen or close until it ends. */
  inCall: boolean;
  /** A message send or inbound read is using it; `done` settles when it ends. */
  message: { done: Promise<void>; finish(): void } | null;
  /** AgentSDR let it go while in use: close it once the call and message end. */
  releaseAfterUse: boolean;
};

/** A ready number held for a message send or inbound read. Pair with done(). */
export type MessageHold = { station: WorkerStation; ready: ReadyWhatsApp; done(): Promise<void> };

const inUse = (slot: Slot) => slot.inCall || slot.message !== null;

export const RECYCLE_MS = 4 * 60 * 60 * 1000;
const MAX_RETRY_MS = 10 * 60 * 1000;
/** How long a call, a link or a close waits for a message already on the number (a send times out at 45 s). */
export const MESSAGE_WAIT_MS = 50_000;

const waitAtMost = (p: Promise<unknown>, ms: number) =>
  new Promise<boolean>((resolve) => {
    const t = setTimeout(() => resolve(false), ms);
    void p.then(() => {
      clearTimeout(t);
      resolve(true);
    });
  });

export class OpenStations {
  private readonly slots = new Map<string, Slot>();
  private openQueue: Promise<void> = Promise.resolve();
  /** Closes in progress (each saves a profile, ~10 s): shutdown waits for them. */
  private readonly closing = new Set<Promise<void>>();
  private ticking = false;
  private stopped = false;

  constructor(
    private readonly capacity: number,
    private readonly deps: OpenStationsDeps,
    private readonly recycleMs = RECYCLE_MS,
    private readonly messageWaitMs = MESSAGE_WAIT_MS,
  ) {}

  /** Station ids held, open or not. */
  held(): string[] {
    return [...this.slots.keys()];
  }

  state(stationId: string): Slot["state"] | null {
    return this.slots.get(stationId)?.state ?? null;
  }

  /** Numbers open, ready and unused right now: what a message may take. */
  idleReady(): { station: WorkerStation; ready: ReadyWhatsApp }[] {
    const out: { station: WorkerStation; ready: ReadyWhatsApp }[] = [];
    for (const slot of this.slots.values()) {
      if (slot.state === "ready" && slot.ready && !inUse(slot) && !slot.releaseAfterUse && !this.stopped) {
        out.push({ station: slot.station, ready: slot.ready });
      }
    }
    return out;
  }

  /**
   * For a message send or inbound read on `stationId`: its WhatsApp Web if it
   * is ready and unused right now (then held until done()), else null. Never waits.
   */
  acquireIdle(stationId: string): MessageHold | null {
    const slot = this.slots.get(stationId);
    if (!slot || this.stopped || slot.state !== "ready" || !slot.ready || inUse(slot) || slot.releaseAfterUse) return null;
    let finish = () => {};
    const done = new Promise<void>((resolve) => (finish = resolve));
    const hold = { done, finish };
    slot.message = hold;
    return {
      station: slot.station,
      ready: slot.ready,
      done: async () => {
        if (slot.message !== hold) return;
        slot.message = null;
        hold.finish();
        if (this.slots.get(stationId) === slot && slot.releaseAfterUse && !slot.inCall) {
          await this.drop(stationId, "no longer to be kept open");
        }
      },
    };
  }

  async tick(): Promise<void> {
    if (this.ticking || this.stopped) return;
    this.ticking = true;
    try {
      let lease: WorkerLeaseResponse;
      try {
        lease = await this.deps.lease(this.held(), this.capacity);
      } catch (error) {
        this.deps.log(`open numbers: lease renewal failed: ${error instanceof Error ? error.message : String(error)}`);
        return;
      }
      for (const id of lease.release) {
        const slot = this.slots.get(id);
        if (!slot) continue;
        if (inUse(slot)) slot.releaseAfterUse = true;
        else await this.drop(id, "no longer to be kept open");
      }
      for (const station of lease.granted) {
        if (!this.slots.has(station.id)) this.startOpening(station);
      }
      const now = this.deps.now();
      for (const [id, slot] of this.slots) {
        if (inUse(slot)) continue;
        if (slot.state === "failed" && now >= slot.retryAt) {
          this.startOpening(slot.station, slot.failures);
        } else if (slot.state === "ready" && slot.ready) {
          const health = await this.deps.health(slot.ready, slot.station).catch(() => "gone" as const);
          if (inUse(slot)) continue;
          if (health === "logged_out") await this.drop(id, "WhatsApp Web is logged out");
          else if (health === "gone") await this.reopen(slot, "its WhatsApp Web closed or crashed");
          else if (now - slot.openedAt >= this.recycleMs) await this.reopen(slot, "routine restart (saves the profile)");
        }
      }
    } finally {
      this.ticking = false;
    }
  }

  /**
   * For a call on `stationId`: its open WhatsApp Web (waiting if it is still
   * opening), or null to open a browser for the call — the number is then
   * marked in a call, so it is not reopened under it, and no new message
   * takes it. A message already on it is waited for first (bounded). Pair with done().
   */
  async acquire(stationId: string, timeoutMs = 90_000): Promise<ReadyWhatsApp | null> {
    const slot = this.slots.get(stationId);
    if (!slot) return null;
    slot.inCall = true;
    if (slot.message) {
      this.deps.log(`open numbers: call on ${slot.station.name} waits for a message in progress`);
      if (!(await waitAtMost(slot.message.done, this.messageWaitMs))) {
        this.deps.log(`open numbers: the message on ${slot.station.name} did not finish in ${Math.round(this.messageWaitMs / 1000)} s; the call goes ahead`);
      }
    }
    if (slot.state === "opening" && slot.opening) {
      await Promise.race([slot.opening, new Promise((resolve) => setTimeout(resolve, timeoutMs))]);
    }
    return slot.state === "ready" ? slot.ready : null;
  }

  /** The call on `stationId` is over. */
  async done(stationId: string): Promise<void> {
    const slot = this.slots.get(stationId);
    if (!slot) return;
    slot.inCall = false;
    if (slot.message) return; // the message's done() closes it if it was let go
    if (slot.releaseAfterUse) await this.drop(stationId, "no longer to be kept open");
    // Opened for the call instead (it was not ready): the next tick retries.
    else if (slot.state === "failed") slot.retryAt = this.deps.now();
  }

  /** Before linking `stationId`: its browser must not be open twice. AgentSDR stops renewing it while it waits to be linked. */
  async closeFor(stationId: string): Promise<void> {
    await this.drop(stationId, "closing it to link WhatsApp Web");
  }

  /** On shutdown: close every number (saving the profiles) and give the leases back. */
  async shutdown(): Promise<void> {
    this.stopped = true;
    await Promise.all(this.held().map((id) => this.drop(id, "worker stopping")));
    // A number let go just before the stop is still saving its profile: exiting now would cut that short.
    await Promise.all([...this.closing]);
    await this.deps.lease([], 0).catch(() => {});
  }

  private startOpening(station: WorkerStation, failures = 0): void {
    const slot: Slot = {
      station,
      state: "opening",
      ready: null,
      opening: null,
      openedAt: 0,
      failures,
      retryAt: 0,
      inCall: this.slots.get(station.id)?.inCall ?? false,
      message: null,
      releaseAfterUse: false,
    };
    this.slots.set(station.id, slot);
    // One at a time: each opening is a browser start and a WhatsApp load.
    const run = async () => {
      if (this.slots.get(station.id) !== slot || this.stopped) return;
      this.deps.log(`open numbers: opening ${station.name}`);
      const result = await this.deps.open(station).catch((error: unknown) => ({ error: error instanceof Error ? error.message : String(error) }));
      if (this.slots.get(station.id) !== slot || this.stopped) {
        if (!("error" in result)) await this.deps.close(result, station).catch(() => {});
        return;
      }
      if ("error" in result) {
        slot.state = "failed";
        slot.failures += 1;
        slot.retryAt = this.deps.now() + Math.min(60_000 * 2 ** (slot.failures - 1), MAX_RETRY_MS);
        this.deps.log(`open numbers: ${station.name} did not open (${result.error}); retrying in ${Math.round((slot.retryAt - this.deps.now()) / 1000)} s`);
        return;
      }
      slot.ready = result;
      slot.state = "ready";
      slot.openedAt = this.deps.now();
      slot.failures = 0;
      this.deps.log(`open numbers: ${station.name} ready`);
    };
    slot.opening = this.openQueue = this.openQueue.then(run, run);
  }

  private async reopen(slot: Slot, why: string): Promise<void> {
    this.deps.log(`open numbers: reopening ${slot.station.name} — ${why}`);
    slot.state = "closing";
    if (slot.ready) await this.track(this.deps.close(slot.ready, slot.station));
    slot.ready = null;
    this.startOpening(slot.station);
  }

  private async drop(stationId: string, why: string): Promise<void> {
    const slot = this.slots.get(stationId);
    if (!slot) return;
    this.slots.delete(stationId);
    this.deps.log(`open numbers: closing ${slot.station.name} — ${why}`);
    if (slot.message && !(await waitAtMost(slot.message.done, this.messageWaitMs))) {
      this.deps.log(`open numbers: the message on ${slot.station.name} did not finish in ${Math.round(this.messageWaitMs / 1000)} s; closing anyway`);
    }
    if (slot.state === "opening" && slot.opening) await slot.opening.catch(() => {});
    if (slot.ready) await this.track(this.deps.close(slot.ready, slot.station));
  }

  private track(close: Promise<void>): Promise<void> {
    const settled = close.catch(() => {});
    this.closing.add(settled);
    void settled.then(() => this.closing.delete(settled));
    return settled;
  }
}
