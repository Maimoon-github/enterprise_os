import {
  MAX_INBOUND_BATCH,
  type StationInboundMessage,
  type StationInboundSource,
  type WorkerInboundRequest,
  type WorkerInboundResponse,
  type WorkerMessageJob,
  type WorkerMessageResultRequest,
  type WorkerStation,
} from "../../../src/lib/calls/stationContract";
import type { StationWorker } from "./extension";
import type { ReadyWhatsApp } from "./jobs";
import type { MessageHold } from "./openStations";

/**
 * AgentSDR's own WhatsApp messaging through the numbers this worker keeps
 * open (KEEP_OPEN > 0). One loop, one thing at a time:
 *
 * - **Send.** Offer AgentSDR the open numbers that are ready, unused and whose
 *   extension can message (0.21.0+); it hands back at most one job (it spaces
 *   sends per number itself). The number is held for the send (acquireIdle) so
 *   no check, restart or close happens under it, sent through the extension
 *   (agentsdrStation.sendMessage, 45 s at most), released, then the result
 *   reported. A call that wants the number meanwhile waits for the send to end.
 * - **Receive.** Every INBOUND_POLL_MS, and soon after a call on a number ends,
 *   each idle number's extension buffer is taken (agentsdrStation.takeInbound)
 *   and posted to /stations/:id/inbound in batches. A batch whose post fails
 *   stays queued in memory and goes first next time.
 *
 * Calls keep priority: the claim loop in main.ts never waits on this one,
 * except for a send already on the number it wants (bounded, see OpenStations).
 */

export type MessagingExtension = Pick<StationWorker, "version" | "supportsMessaging" | "sendMessage" | "takeInbound">;

export type MessagingDeps = {
  idleReady(): { station: WorkerStation; ready: ReadyWhatsApp }[];
  acquireIdle(stationId: string): MessageHold | null;
  claim(stations: string[]): Promise<WorkerMessageJob | null>;
  report(messageId: string, body: WorkerMessageResultRequest): Promise<void>;
  postInbound(stationId: string, body: WorkerInboundRequest): Promise<WorkerInboundResponse>;
  /** The recorder extension in this number's browser. */
  connect(ready: ReadyWhatsApp): Promise<MessagingExtension>;
  log(text: string): void;
  now(): number;
  sleep(ms: number): Promise<void>;
};

export type MessagingOptions = {
  messagePollMs: number;
  inboundPollMs: number;
  sendTimeoutMs?: number;
  takeTimeoutMs?: number;
  /** Waits between attempts to report a send's result. */
  reportRetryDelaysMs?: number[];
  /** Unposted inbound messages kept per number. */
  pendingCap?: number;
  /** After the extension could not be reached, try again after this long. */
  connectRetryMs?: number;
};

export const SEND_TIMEOUT_MS = 45_000;
const TAKE_TIMEOUT_MS = 15_000;
const REPORT_RETRY_DELAYS_MS = [1000, 2000, 4000, 8000, 15_000, 30_000];
export const PENDING_INBOUND_CAP = 1000;
const CONNECT_RETRY_MS = 5 * 60 * 1000;
const MAX_ERROR_BACKOFF_MS = 30_000;

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e)).split("\n")[0];

const TIMED_OUT = Symbol("timed out");
function withTimeout<T>(p: Promise<T>, ms: number): Promise<T | typeof TIMED_OUT> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return Promise.race([
    p.finally(() => clearTimeout(timer)),
    new Promise<typeof TIMED_OUT>((resolve) => (timer = setTimeout(() => resolve(TIMED_OUT), ms))),
  ]);
}

type Pending = { source: StationInboundSource; message: StationInboundMessage };

/** Splits queued messages into posts: at most `max` each, one source per post, in order. */
export function inboundBatches(items: Pending[], max = MAX_INBOUND_BATCH): WorkerInboundRequest[] {
  const out: WorkerInboundRequest[] = [];
  for (const { source, message } of items) {
    const last = out.at(-1);
    if (last && last.source === source && last.messages.length < max) last.messages.push(message);
    else out.push({ source, messages: [message] });
  }
  return out;
}

/** Inbound messages not yet posted, per number, oldest first, capped. */
export class InboundQueue {
  private readonly pending = new Map<string, Pending[]>();

  constructor(
    private readonly log: (text: string) => void,
    private readonly cap = PENDING_INBOUND_CAP,
  ) {}

  add(stationId: string, source: StationInboundSource, messages: StationInboundMessage[]): void {
    if (!messages.length) return;
    const list = this.pending.get(stationId) ?? [];
    list.push(...messages.map((message) => ({ source, message })));
    if (list.length > this.cap) {
      const dropped = list.splice(0, list.length - this.cap).length;
      this.log(`messages: ${dropped} received message(s) on station ${stationId} dropped unposted (more than ${this.cap} waiting)`);
    }
    this.pending.set(stationId, list);
  }

  size(stationId: string): number {
    return this.pending.get(stationId)?.length ?? 0;
  }

  stations(): string[] {
    return [...this.pending.keys()];
  }

  /** Posts what is queued for `stationId`, in order; stops at the first failed post and keeps the rest. */
  async flush(stationId: string, post: (body: WorkerInboundRequest) => Promise<unknown>): Promise<{ posted: number; error?: string }> {
    const list = this.pending.get(stationId);
    let posted = 0;
    if (!list) return { posted };
    for (const batch of inboundBatches(list)) {
      try {
        await post(batch);
      } catch (e) {
        return { posted, error: errorText(e) };
      }
      list.splice(0, batch.messages.length);
      posted += batch.messages.length;
    }
    this.pending.delete(stationId);
    return { posted };
  }
}

type ExtensionEntry = {
  browser: unknown;
  state: "connecting" | "ready" | "failed";
  extension: MessagingExtension | null;
  retryAt: number;
};

export class Messaging {
  readonly inbound: InboundQueue;
  private readonly extensions = new Map<string, ExtensionEntry>();
  private readonly toldUnsupported = new Set<string>();
  private readonly lastSource = new Map<string, StationInboundSource>();
  /** Numbers whose inbound should be read soon (a call on them just ended). */
  private readonly due = new Set<string>();
  private stopped = false;
  private running: Promise<void> | null = null;
  private wake: (() => void) | null = null;
  private nextInboundAt = 0;

  constructor(
    private readonly deps: MessagingDeps,
    private readonly options: MessagingOptions,
  ) {
    this.inbound = new InboundQueue(deps.log, options.pendingCap);
  }

  start(): void {
    this.nextInboundAt = this.deps.now() + this.options.inboundPollMs;
    this.running ??= this.loop();
  }

  /** Stops claiming; an in-flight send finishes and is reported, then what was received is posted once more. */
  async stop(): Promise<void> {
    this.stopped = true;
    this.wake?.();
    await this.running;
  }

  /** A call on `stationId` ended: read what arrived meanwhile, without making the caller wait. */
  afterCall(stationId: string): void {
    this.due.add(stationId);
    this.wake?.();
  }

  private async loop(): Promise<void> {
    let backoff = 0;
    while (!this.stopped) {
      try {
        const now = this.deps.now();
        if (now >= this.nextInboundAt) {
          this.nextInboundAt = now + this.options.inboundPollMs;
          this.due.clear();
          await this.inboundPass();
        } else if (this.due.size) {
          // Best effort: a number busy again by now is read on the next full pass.
          const only = new Set(this.due);
          this.due.clear();
          await this.inboundPass(only);
        }
        if (this.stopped) break;
        const sent = await this.messageOnce();
        backoff = 0;
        // After a job there may be more: claim again straight away.
        if (!sent) await this.idle(this.options.messagePollMs);
      } catch (e) {
        backoff = Math.min(backoff ? backoff * 2 : 1000, MAX_ERROR_BACKOFF_MS);
        this.deps.log(`messages: ${errorText(e)} (retry in ${backoff / 1000}s)`);
        await this.idle(backoff);
      }
    }
    // Last read before the numbers close: their extension's buffer goes with the browser.
    await this.inboundPass().catch((e: unknown) => this.deps.log(`messages: last inbound read failed: ${errorText(e)}`));
    for (const id of this.inbound.stations()) {
      this.deps.log(`messages: ${this.inbound.size(id)} received message(s) on station ${id} were never posted`);
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
   * The extension on this number if it can message; null while it is being
   * reached, when it could not be, or when it is older than 0.21.0 (said once
   * per number). Re-reached when the number's browser changes (reopened).
   */
  extensionFor(station: WorkerStation, ready: ReadyWhatsApp): MessagingExtension | null {
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
          if (extension.supportsMessaging) this.toldUnsupported.delete(station.id);
          else if (!this.toldUnsupported.has(station.id)) {
            this.toldUnsupported.add(station.id);
            this.deps.log(`messages: ${station.name}'s recorder extension is ${extension.version}; messaging needs 0.21.0+ — not sending or reading messages on it`);
          }
        },
        (e: unknown) => {
          if (this.extensions.get(station.id) !== fresh) return;
          fresh.state = "failed";
          fresh.retryAt = this.deps.now() + (this.options.connectRetryMs ?? CONNECT_RETRY_MS);
          this.deps.log(`messages: could not reach ${station.name}'s recorder extension: ${errorText(e)}`);
        },
      );
      return null;
    }
    return entry!.state === "ready" && entry!.extension?.supportsMessaging ? entry!.extension : null;
  }

  /** One claim, and the send if a job came back. True when a job was handled. */
  async messageOnce(): Promise<boolean> {
    const offered = new Map<string, { station: WorkerStation; ready: ReadyWhatsApp; extension: MessagingExtension }>();
    for (const { station, ready } of this.deps.idleReady()) {
      const extension = this.extensionFor(station, ready);
      if (extension) offered.set(station.id, { station, ready, extension });
    }
    if (!offered.size || this.stopped) return false;
    const job = await this.deps.claim([...offered.keys()]);
    if (!job) return false;
    const target = offered.get(job.stationId);
    const hold = target ? this.deps.acquireIdle(job.stationId) : null;
    if (!target || !hold || hold.ready.browser !== target.ready.browser) {
      await hold?.done();
      this.deps.log(`messages: message ${job.id} came for station ${job.stationId}, which is busy; handing it back`);
      await this.report(job.id, { ok: false, retryable: true, error: "station busy" });
      return true;
    }
    const startedAt = this.deps.now();
    let body: WorkerMessageResultRequest;
    try {
      const result = await withTimeout(target.extension.sendMessage({ phone: job.phone, text: job.body }), this.options.sendTimeoutMs ?? SEND_TIMEOUT_MS);
      if (result === TIMED_OUT) body = { ok: false, retryable: false, uncertain: true, error: "timed out — may have been sent" };
      else if (!result || typeof result !== "object" || typeof result.ok !== "boolean") body = { ok: false, retryable: false, error: "the extension gave no answer" };
      else if (result.ok) body = { ok: true, providerMessageId: result.providerMessageId ?? null, sentAt: this.deps.now() };
      else body = { ok: false, retryable: result.retryable === true, uncertain: result.uncertain === true, error: result.error || "send failed" };
    } catch (e) {
      // It may have failed after WhatsApp took the message: never retried.
      body = { ok: false, retryable: false, uncertain: true, error: `extension: ${errorText(e)}` };
    } finally {
      await hold.done();
    }
    const took = Math.round((this.deps.now() - startedAt) / 100) / 10;
    this.deps.log(
      `messages: ${job.id} via ${target.station.name}: ${body.ok ? "sent" : `not sent (${body.error}${body.retryable ? ", retryable" : ""})`} in ${took} s`,
    );
    await this.report(job.id, body);
    return true;
  }

  private async report(messageId: string, body: WorkerMessageResultRequest): Promise<void> {
    const delays = this.options.reportRetryDelaysMs ?? REPORT_RETRY_DELAYS_MS;
    for (let attempt = 0; ; attempt++) {
      try {
        await this.deps.report(messageId, body);
        return;
      } catch (e) {
        if (attempt >= delays.length) {
          this.deps.log(`messages: gave up reporting ${messageId} (${JSON.stringify(body)}): ${errorText(e)}`);
          return;
        }
        this.deps.log(`messages: reporting ${messageId} failed (${errorText(e)}); retrying in ${delays[attempt] / 1000}s`);
        await this.deps.sleep(delays[attempt]);
      }
    }
  }

  /** Reads each idle number's received messages (only `only`, when given) and posts what is queued. */
  async inboundPass(only?: Set<string>): Promise<void> {
    for (const { station, ready } of this.deps.idleReady()) {
      if (only && !only.has(station.id)) continue;
      const extension = this.extensionFor(station, ready);
      if (!extension) continue;
      const hold = this.deps.acquireIdle(station.id);
      if (!hold) continue;
      try {
        const take = await withTimeout(extension.takeInbound(), this.options.takeTimeoutMs ?? TAKE_TIMEOUT_MS);
        if (take === TIMED_OUT) this.deps.log(`messages: reading ${station.name}'s received messages timed out`);
        else if (take && typeof take === "object") {
          if (this.lastSource.get(station.id) !== take.source) {
            this.lastSource.set(station.id, take.source);
            this.deps.log(
              `messages: ${station.name} reads received messages from ${take.source === "store" ? "WhatsApp's message store" : take.source === "dom" ? "the page (DOM)" : "nowhere — the extension cannot read them"}`,
            );
          }
          this.inbound.add(station.id, take.source, Array.isArray(take.messages) ? take.messages : []);
        }
      } catch (e) {
        this.deps.log(`messages: reading ${station.name}'s received messages failed: ${errorText(e)}`);
      } finally {
        await hold.done();
      }
    }
    for (const id of this.inbound.stations()) {
      if (only && !only.has(id)) continue;
      const { posted, error } = await this.inbound.flush(id, (body) => this.deps.postInbound(id, body));
      if (error) this.deps.log(`messages: posting received messages for station ${id} failed (${error}); ${this.inbound.size(id)} kept for next time`);
      else if (posted) this.deps.log(`messages: posted ${posted} received message(s) for station ${id}`);
    }
  }
}
