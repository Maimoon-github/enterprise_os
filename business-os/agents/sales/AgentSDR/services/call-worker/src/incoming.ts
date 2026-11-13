import {
  INCOMING_CALL_MAX_AGE_MS,
  type StationIncomingCall,
  type WorkerCall,
  type WorkerIncomingCallRequest,
  type WorkerIncomingCallResponse,
  type WorkerStation,
} from "../../../src/lib/calls/stationContract";
import type { StationWorker } from "./extension";
import type { ReadyWhatsApp } from "./jobs";

/**
 * Incoming calls: a lead who calls a station's number back is answered by the
 * AI agent (KEEP_OPEN > 0, extension 0.22.0+). One loop, beside messaging:
 *
 * Every INCOMING_POLL_MS, each open number that is ready and unused has its
 * rings taken (agentsdrStation.takeIncomingCalls — a read of the extension's
 * own storage, which never touches the page, so the number is not held for
 * it and messaging is not held up). Each new ring young enough to answer goes
 * to AgentSDR (POST /stations/:id/incoming), which decides. On `answer: true`
 * the call row already exists, claimed by this worker, and the call runs at
 * once — concurrently, not in the claim loop, which may be in another call
 * on another number — through runCall's answer path. Anything else, or a
 * failed post, lets it ring out.
 */

export type IncomingExtension = Pick<StationWorker, "version" | "supportsIncoming" | "takeIncomingCalls">;

export type IncomingDeps = {
  idleReady(): { station: WorkerStation; ready: ReadyWhatsApp }[];
  /** The recorder extension in this number's browser. */
  connect(ready: ReadyWhatsApp): Promise<IncomingExtension>;
  /** Asks AgentSDR whether to answer. */
  ask(stationId: string, body: WorkerIncomingCallRequest): Promise<WorkerIncomingCallResponse>;
  /** Runs the answered call on the number to its end (holds the number meanwhile). */
  answer(station: WorkerStation, call: WorkerCall, ring: StationIncomingCall): Promise<void>;
  workerId: string;
  log(text: string): void;
  now(): number;
};

export type IncomingOptions = {
  pollMs: number;
  takeTimeoutMs?: number;
  /** After the extension could not be reached, try again after this long. */
  connectRetryMs?: number;
};

const TAKE_TIMEOUT_MS = 5_000;
const CONNECT_RETRY_MS = 5 * 60 * 1000;
/** Rings remembered as handled (they are offered once each). */
const HANDLED_MAX = 1000;

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e)).split("\n")[0];

const TIMED_OUT = Symbol("timed out");
function withTimeout<T>(p: Promise<T>, ms: number): Promise<T | typeof TIMED_OUT> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return Promise.race([
    p.finally(() => clearTimeout(timer)),
    new Promise<typeof TIMED_OUT>((resolve) => (timer = setTimeout(() => resolve(TIMED_OUT), ms))),
  ]);
}

type ExtensionEntry = {
  browser: unknown;
  state: "connecting" | "ready" | "failed";
  extension: IncomingExtension | null;
  retryAt: number;
};

export class Incoming {
  private readonly extensions = new Map<string, ExtensionEntry>();
  private readonly toldUnsupported = new Set<string>();
  /** "<station id> <waCallId>", oldest first. */
  private readonly handled = new Set<string>();
  /** Numbers with an answered call running (until its answer() settles). */
  private readonly answering = new Map<string, Promise<void>>();
  private stopped = false;
  private running: Promise<void> | null = null;
  private wake: (() => void) | null = null;

  constructor(
    private readonly deps: IncomingDeps,
    private readonly options: IncomingOptions,
  ) {}

  start(): void {
    this.running ??= this.loop();
  }

  /** Stops answering; the calls already answered run to their end. */
  async stop(): Promise<void> {
    this.stopped = true;
    this.wake?.();
    await this.running;
    await Promise.all([...this.answering.values()]);
  }

  private async loop(): Promise<void> {
    while (!this.stopped) {
      try {
        await this.pollOnce();
      } catch (e) {
        this.deps.log(`incoming: ${errorText(e)}`);
      }
      await this.idle(this.options.pollMs);
    }
  }

  private idle(ms: number): Promise<void> {
    if (this.stopped) return Promise.resolve();
    return new Promise((resolve) => {
      const t = setTimeout(done, ms);
      function done() {
        clearTimeout(t);
        resolve();
      }
      this.wake = done;
    });
  }

  /**
   * The extension on this number if it can answer calls; null while it is
   * being reached, when it could not be, or when it is older than 0.22.0
   * (said once per number). Re-reached when the number's browser changes.
   */
  extensionFor(station: WorkerStation, ready: ReadyWhatsApp): IncomingExtension | null {
    let entry = this.extensions.get(station.id);
    const stale = !entry || entry.browser !== ready.browser || (entry.state === "failed" && this.deps.now() >= entry.retryAt);
    if (stale) {
      const fresh: ExtensionEntry = { browser: ready.browser, state: "connecting", extension: null, retryAt: 0 };
      entry = fresh;
      this.extensions.set(station.id, fresh);
      void this.deps.connect(ready).then(
        (extension) => {
          if (this.extensions.get(station.id) !== fresh) return;
          fresh.extension = extension;
          fresh.state = "ready";
          if (extension.supportsIncoming) this.toldUnsupported.delete(station.id);
          else if (!this.toldUnsupported.has(station.id)) {
            this.toldUnsupported.add(station.id);
            this.deps.log(`incoming: ${station.name}'s recorder extension is ${extension.version}; answering calls needs 0.22.0+ — its calls ring out`);
          }
        },
        (e: unknown) => {
          if (this.extensions.get(station.id) !== fresh) return;
          fresh.state = "failed";
          fresh.retryAt = this.deps.now() + (this.options.connectRetryMs ?? CONNECT_RETRY_MS);
          this.deps.log(`incoming: could not reach ${station.name}'s recorder extension: ${errorText(e)}`);
        },
      );
      return null;
    }
    return entry!.state === "ready" && entry!.extension?.supportsIncoming ? entry!.extension : null;
  }

  /** One look at every idle number: takes its rings and answers the first AgentSDR wants answered. */
  async pollOnce(): Promise<void> {
    for (const { station, ready } of this.deps.idleReady()) {
      if (this.stopped) return;
      if (this.answering.has(station.id)) continue;
      const extension = this.extensionFor(station, ready);
      if (!extension) continue;
      let rings: StationIncomingCall[];
      try {
        const taken = await withTimeout(extension.takeIncomingCalls(), this.options.takeTimeoutMs ?? TAKE_TIMEOUT_MS);
        if (taken === TIMED_OUT) {
          this.deps.log(`incoming: reading ${station.name}'s ringing calls timed out`);
          continue;
        }
        rings = Array.isArray(taken) ? taken : [];
      } catch (e) {
        this.deps.log(`incoming: reading ${station.name}'s ringing calls failed: ${errorText(e)}`);
        continue;
      }
      for (const ring of rings) {
        if (await this.consider(station, ring)) break; // one call at a time on a number; the rest ring out
      }
    }
  }

  /** True when the ring was answered. */
  private async consider(station: WorkerStation, ring: StationIncomingCall): Promise<boolean> {
    if (!ring || typeof ring.waCallId !== "string" || !ring.waCallId) return false;
    const key = `${station.id} ${ring.waCallId}`;
    if (this.handled.has(key)) return false;
    this.remember(key);
    const age = this.deps.now() - ring.at;
    if (age > INCOMING_CALL_MAX_AGE_MS) {
      this.deps.log(`incoming: a ring on ${station.name} is ${Math.round(age / 1000)} s old — letting it ring`);
      return false;
    }
    if (this.stopped) return false;
    this.deps.log(`incoming: ringing on ${station.name}`);
    let response: WorkerIncomingCallResponse;
    try {
      response = await this.deps.ask(station.id, { workerId: this.deps.workerId, call: ring });
    } catch (e) {
      this.deps.log(`incoming: could not ask AgentSDR (${errorText(e)}) — letting it ring`);
      return false;
    }
    if (!response?.answer) {
      this.deps.log(`incoming: not answering (${response?.reason ?? "no answer from AgentSDR"})`);
      return false;
    }
    this.deps.log(`incoming: answering (call ${response.call.id})`);
    const run = this.deps
      .answer(station, response.call, ring)
      .catch((e: unknown) => this.deps.log(`incoming: call ${response.call.id} failed: ${errorText(e)}`))
      .finally(() => this.answering.delete(station.id));
    this.answering.set(station.id, run);
    return true;
  }

  private remember(key: string): void {
    this.handled.add(key);
    if (this.handled.size > HANDLED_MAX) {
      const oldest = this.handled.values().next().value;
      if (oldest !== undefined) this.handled.delete(oldest);
    }
  }
}
