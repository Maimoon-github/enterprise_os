import type { Page } from "playwright-core";
import type { WorkerJob, WorkerStation } from "../../../src/lib/calls/stationContract";
import { MAX_TIMELINE_ENTRIES, type CallTimelineEntry } from "../../../src/lib/calls/stationContract";
import { getCallStatus, releaseCall, reportStationState, saveTimeline } from "./api";
import { config } from "./config";
import { REP_CALL_MIN_VERSION, stationCallRequest, stationWorker, type StationResult, type StationWorker } from "./extension";
import { firstLine, openStationBrowser, type StationBrowser } from "./launchers";
import { log } from "./log";
import {
  backToQr,
  dismissDialogs,
  loggedInPhone,
  isEnglish,
  isLoginScreen,
  openWhatsApp,
  screenshotDataUrl,
  startPhoneNumberLogin,
  waitForReady,
  waitForWhatsAppState,
  whatsAppLanguage,
} from "./whatsapp";

const NOT_ENGLISH = (language: string) =>
  `WhatsApp Web is in "${language}" — set this profile's browser language to English (in GoLogin: profile → Navigator → Language, not based on IP)`;

type CallJob = Extract<WorkerJob, { kind: "call" }>;
type LinkJob = Extract<WorkerJob, { kind: "link" }>;

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const digitsOf = (phone: string) => phone.replace(/\D/g, "");

/** One readable line for the app; the full error goes to the log. */
const message = (e: unknown) => firstLine(e);

/** The calls running, so a shutdown can hang them up: a claimed call, and incoming ones answered beside it. */
const running = new Map<string, StationWorker | null>();
let stopping = false;

export function activeCallsForShutdown(): { callId: string; worker: StationWorker | null }[] {
  return [...running].map(([callId, worker]) => ({ callId, worker }));
}

export function requestStop(): void {
  stopping = true;
}

async function safeRelease(callId: string, error: string): Promise<void> {
  try {
    await releaseCall(callId, error);
  } catch (e) {
    log(`call ${callId}: release failed: ${message(e)}`);
  }
}

async function safeState(stationId: string, body: Parameters<typeof reportStationState>[1]): Promise<void> {
  try {
    await reportStationState(stationId, body);
  } catch (e) {
    log(`station ${stationId}: state report failed: ${message(e)}`);
  }
}

async function waitDone(callId: string, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if ((await getCallStatus(callId)).done) return true;
    } catch (e) {
      log(`call ${callId}: status check failed: ${message(e)}`);
    }
    await sleep(3000);
  }
  return false;
}

/** A number's WhatsApp Web, open and checked: ready to place a call. */
export type ReadyWhatsApp = { browser: StationBrowser; page: Page };

/**
 * Opens WhatsApp Web in `browser` and checks it can place calls: logged in,
 * in English, as the number's own account. Reports the station's state as it
 * goes (logged out, wrong account, active). Returns the reason it cannot
 * call, or the page.
 */
export async function prepareWhatsApp(
  station: WorkerStation,
  browser: StationBrowser,
  step: (text: string) => void,
): Promise<{ page: Page } | { error: string }> {
  const page = await openWhatsApp(browser.context);
  step("WhatsApp Web page opened");
  step("waiting for WhatsApp Web");
  const state = await waitForWhatsAppState(page, 120_000);
  if (state === "logged_out") {
    step("WhatsApp Web is logged out");
    const error = `WhatsApp Web on ${station.name} is logged out — link it again`;
    await safeState(station.id, { status: "logged_out", error });
    return { error };
  }
  if (state === "timeout") {
    step("WhatsApp Web did not load");
    return { error: `WhatsApp Web on ${station.name} did not load in time` };
  }
  step("WhatsApp Web ready (chats showing)");
  const language = await whatsAppLanguage(page);
  if (!isEnglish(language)) {
    // The extension cannot find WhatsApp's buttons in another language.
    step(`WhatsApp Web is in ${language}`);
    await safeState(station.id, { error: NOT_ENGLISH(language) });
    return { error: NOT_ENGLISH(language) };
  }
  // Calls go out from whichever account WhatsApp Web is logged in as.
  const linkedPhone = await loggedInPhone(page);
  if (linkedPhone && digitsOf(linkedPhone) !== digitsOf(station.phone)) {
    const error = `WhatsApp Web is logged in as ${linkedPhone}, not ${station.phone} — not calling from the wrong number`;
    step(error);
    await safeState(station.id, { linkedPhone });
    return { error };
  }
  await safeState(station.id, { status: "active", error: null, ...(linkedPhone ? { linkedPhone } : {}) });
  const dialogs = await dismissDialogs(page);
  if (dialogs) step(`closed ${dialogs} WhatsApp dialog(s) over the chats`);
  return { page };
}

/**
 * Places a cloud call. `open` is the number's WhatsApp Web already open
 * (openStations.ts) — used as is and left open; without it, a browser is
 * opened for this call and closed after. With `answer`, the call is an
 * incoming one ringing on the open number (src/incoming.ts): the extension
 * answers ring `answer.waCallId` instead of dialing; the rest is the same.
 */
export async function runCall(job: CallJob, open: ReadyWhatsApp | null = null, answer: { waCallId: string } | null = null): Promise<void> {
  const { station, call } = job;
  const cfg = config();
  const tag = `call ${call.id} @ ${station.name}`;
  let browser: StationBrowser | null = open?.browser ?? null;
  let released = false;
  let stopExtensionLog = async () => {};
  let stopWatching = () => {};
  // Every timed step of the call, the worker's and the extension's, saved
  // with the call (call_sessions.timeline) as it goes and at the end.
  const timeline: CallTimelineEntry[] = [];
  const step = (text: string) => {
    log(`${tag}: ${text}`);
    timeline.push({ at: Date.now(), source: "worker", text });
  };
  const flushTimeline = () =>
    saveTimeline(call.id, timeline.slice(-MAX_TIMELINE_ENTRIES)).catch((e) => log(`${tag}: timeline not saved: ${message(e)}`));
  step(answer ? `incoming call, answered by ${cfg.workerId}` : `claimed by ${cfg.workerId}`);
  const release = async (error: string) => {
    released = true;
    await safeRelease(call.id, error);
  };
  try {
    let page: Page;
    if (open) {
      step("using the number's open WhatsApp Web");
      page = open.page;
      if (page.isClosed() || (await isLoginScreen(page))) {
        const error = page.isClosed()
          ? `WhatsApp Web on ${station.name} was closed — try again in a minute`
          : `WhatsApp Web on ${station.name} is logged out — link it again`;
        step(error);
        if (!page.isClosed()) await safeState(station.id, { status: "logged_out", error });
        await release(error);
        return;
      }
      // Not for an incoming call: its ringing screen may be a dialog, and Escape could decline it.
      const dialogs = answer ? 0 : await dismissDialogs(page);
      if (dialogs) step(`closed ${dialogs} WhatsApp dialog(s) over the chats`);
    } else {
      step(`opening browser (${station.launcher})`);
      try {
        browser = await openStationBrowser(station, { note: step });
      } catch (e) {
        step(`browser failed: ${message(e)}`);
        if (e instanceof Error && e.stack) log(`${tag}: ${e.stack.split("\n").slice(0, 8).join("\n  ")}`);
        await release(`Could not open the station's browser: ${message(e)}`);
        return;
      }
      watchConsole(browser, tag);
      const prepared = await prepareWhatsApp(station, browser, step);
      if ("error" in prepared) {
        await release(prepared.error);
        return;
      }
      page = prepared.page;
    }
    const opened = browser!;
    // The browser closing or WhatsApp's tab crashing ends the call with no
    // report from the extension; without this the worker would wait out the
    // whole call timeout with the station held busy.
    let lostReason: (reason: string) => void = () => {};
    const lost = new Promise<string>((resolve) => (lostReason = resolve));
    const onBrowserClose = () => lostReason("The station's browser closed during the call");
    const onCrash = () => lostReason("WhatsApp Web crashed during the call");
    const onTabClose = () => lostReason("WhatsApp Web's tab closed during the call");
    opened.context.on("close", onBrowserClose);
    page.on("crash", onCrash);
    page.on("close", onTabClose);
    // An open number's browser outlives the call: its listeners must not pile up.
    stopWatching = () => {
      opened.context.off("close", onBrowserClose);
      page.off("crash", onCrash);
      page.off("close", onTabClose);
    };

    let worker: StationWorker;
    try {
      worker = await stationWorker(opened.context);
    } catch (e) {
      await release(message(e));
      return;
    }
    running.set(call.id, worker);
    const request = stationCallRequest(call, new URL(cfg.agentsdrUrl).origin, Date.now());
    // A rep call: the rep talks from their AgentSDR tab; the extension
    // carries the audio both ways through AgentSDR's relay, and dials at once.
    const kind = call.remoteRep ? "rep call (relay)" : "agent call";
    let started: StationResult;
    if (answer) {
      step(`answering the incoming call (extension ${worker.version})`);
      started = call.remoteRep
        ? { ok: false, error: "A rep call is placed, never answered" }
        : worker.supportsIncoming
          ? await worker.answerCall({ ...request, waCallId: answer.waCallId })
          : { ok: false, error: `The recorder extension ${worker.version} cannot answer calls (needs 0.22.0+)` };
    } else if (call.remoteRep && !worker.supportsRepCalls) {
      started = {
        ok: false,
        error: `The recorder extension on ${station.name} is ${worker.version}; talking through a calling number needs ${REP_CALL_MIN_VERSION} or newer — update it`,
      };
    } else {
      step(`starting ${kind} (extension ${worker.version})`);
      started = await worker.startCall(request);
    }
    if (!started.ok) {
      step(`${answer ? "answer" : `${kind} start`} refused: ${started.error}`);
      await release(started.error);
      return;
    }
    step(`${kind} running`);
    // The extension's own log of the call (dialing, the AI's steps, the
    // transcript), fetched — CloakBrowser hides console messages.
    let drained = 0;
    log(`${tag}: tabs: ${opened.context.pages().map((p) => p.url().slice(0, 60)).join(" | ")}`);
    // The extension's call log, written into the WhatsApp page (wa-agent's pageLog) —
    // read from every WhatsApp tab, in case the call runs in one this worker did not open.
    const drain = () =>
      Promise.all(
        opened.context
          .pages()
          .filter((p) => p.url().startsWith("https://web.whatsapp.com"))
          .map((p, index) =>
            p
              .evaluate(() => {
                const element = document.getElementById("agentsdr-station-log");
                const text = element?.getAttribute("data-lines") ?? "";
                element?.setAttribute("data-lines", "");
                return text.split("\n").filter(Boolean);
              })
              .catch(() => [] as string[])
              .then((lines) => lines.map((line) => (p === page ? line : `[tab ${index}] ${line}`))),
          ),
      ).then((perTab) => {
        const lines = perTab.flat();
        drained += lines.length;
        lines.forEach((line) => {
          log(`${tag}: ext ${line}`);
          timeline.push({ at: extensionTime(line), source: "extension", text: line.replace(/^(\[tab \d+\] )?\d\d:\d\d:\d\d\.\d{3} /, "$1") });
        });
      });
    let ticks = 0;
    const extensionLog = setInterval(() => {
      void drain().then(() => {
        // Saved every 10 s too, so a call that dies midway still leaves its steps.
        if (++ticks % 5 === 0) void flushTimeline();
      });
    }, 2_000);
    stopExtensionLog = async () => {
      clearInterval(extensionLog);
      // Read the last lines before the browser closes.
      await drain();
      step(`extension log: ${drained} lines`);
    };
    const outcome = await Promise.race([waitDone(call.id, cfg.callTimeoutMs), lost]);
    if (typeof outcome === "string") {
      step(outcome);
      // The extension may still have reported the end just before; give it a moment.
      if (!(await waitDone(call.id, 5_000))) await release(outcome);
      return;
    }
    let done = outcome;
    if (!done) {
      step("timed out, hanging up");
      await worker.endCall(call.id).catch((e) => step(`endCall failed: ${message(e)}`));
      done = await waitDone(call.id, 30_000);
      if (!done) await release("The call timed out");
    }
    step("finished");
    // A browser opened for this call stays a moment, so the extension's last reports go out.
    if (!open) await sleep(3000);
  } catch (e) {
    step(`error: ${message(e)}`);
    if (!released) await release(`Call worker error: ${message(e)}`);
  } finally {
    await stopExtensionLog();
    stopWatching();
    running.delete(call.id);
    if (browser && !open) {
      step("closing the browser");
      await browser.close().catch((e) => step(`close failed: ${message(e)}`));
      step("browser closed");
    }
    await flushTimeline();
  }
}

/**
 * When the extension logged a line: its lines start with the UTC time of day
 * ("HH:MM:SS.mmm"), dated today — or yesterday, for a line from just before
 * midnight. Falls back to now.
 */
function extensionTime(line: string): number {
  const match = /^(?:\[tab \d+\] )?(\d\d):(\d\d):(\d\d)\.(\d{3}) /.exec(line);
  if (!match) return Date.now();
  const now = new Date();
  const at = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4]));
  return at > now.getTime() + 60_000 ? at - 86_400_000 : at;
}

export async function runLink(job: LinkJob): Promise<void> {
  const { station } = job;
  const tag = `link @ ${station.name}`;
  let browser: StationBrowser | null = null;
  try {
    log(`${tag}: opening browser (${station.launcher})`);
    browser = await openStationBrowser(station, { fresh: job.fresh });
    const page = await openWhatsApp(browser.context);
    const state = await waitForWhatsAppState(page, 90_000);
    if (state === "ready") {
      const linkedPhone = await loggedInPhone(page);
      log(`${tag}: already linked${linkedPhone ? ` as ${linkedPhone}` : ""}`);
      await safeState(station.id, { status: "active", linkDone: true, link: null, error: null, ...(linkedPhone ? { linkedPhone } : {}) });
      return;
    }
    // Neither the chats nor a login screen: an earlier link is still loading the chats.
    const resumingSync = state === "timeout" && !(await isLoginScreen(page));
    if (state === "timeout" && !resumingSync) {
      await safeState(station.id, { linkDone: true, link: null, error: "WhatsApp Web did not load" });
      return;
    }
    const language = await whatsAppLanguage(page);
    // The QR in the screenshot works in any language; the code and calls need English.
    if (!isEnglish(language)) {
      log(`${tag}: WhatsApp Web is in ${language}`);
      await safeState(station.id, { error: NOT_ENGLISH(language) });
    }
    const code = resumingSync || !isEnglish(language) ? null : await startPhoneNumberLogin(page, station.phone, (step) => log(`${tag}: phone login: ${step}`));
    // No code: back to the QR, which the screenshot then shows.
    if (!code && !resumingSync) await backToQr(page);
    log(`${tag}: code ${code ?? "not found (QR only)"}`);
    // Four minutes to link; once the login screen has gone (the phone linked
    // and WhatsApp is loading the chats), up to twelve for the first sync,
    // which is slow in a cloud browser with a long history (12 Oct 2026).
    const startedAt = Date.now();
    let syncing = resumingSync;
    while (Date.now() - startedAt < (syncing ? 12 : 4) * 60_000 && !stopping) {
      if (!syncing && !(await isLoginScreen(page))) {
        syncing = true;
        log(`${tag}: phone linked — waiting for WhatsApp to load the chats`);
      }
      await safeState(station.id, { link: { code, screenshot: await shot(page) } });
      // Waits the whole 8 s unless the chats appear: the login screen stays up until the code is typed.
      if (await waitForReady(page, 8_000)) {
        log(`${tag}: linked`);
        // Let WhatsApp finish storing the new session before the browser closes.
        await sleep(15_000);
        const linkedPhone = await loggedInPhone(page);
        log(`${tag}: logged in as ${linkedPhone ?? "an unknown account"}`);
        await safeState(station.id, { status: "active", link: null, linkDone: true, error: null, ...(linkedPhone ? { linkedPhone } : {}) });
        return;
      }
    }
    log(`${tag}: gave up${syncing ? " (linked, but the chats never finished loading)" : ""}`);
    await safeState(station.id, {
      linkDone: true,
      link: null,
      error: syncing ? "Linked, but WhatsApp Web didn't finish loading the chats — try Relink to let it continue" : "Linking timed out",
    });
  } catch (e) {
    log(`${tag}: error: ${e instanceof Error ? e.message : String(e)}`);
    await safeState(station.id, { linkDone: true, link: null, error: `Linking failed: ${message(e)}` });
  } finally {
    if (browser) await browser.close().catch((e) => log(`${tag}: close failed: ${message(e)}`));
  }
}

/**
 * Mirrors the extension's own messages into the worker's log: the AI agent's
 * steps and transcript ("[agentsdr agent]"), the recorder's warnings, and page
 * errors — the only record of what happened inside a cloud call.
 */
export function watchConsole(browser: StationBrowser | null, tag: string): void {
  if (!browser) return;
  browser.context.on("console", (msg) => {
    const text = msg.text();
    if (/agentsdr|\[recorder\]/i.test(text) || msg.type() === "error") log(`${tag}: [${msg.type()}] ${text.slice(0, 500)}`);
  });
  browser.context.on("weberror", (error) => log(`${tag}: page error: ${error.error().message.slice(0, 300)}`));
}

async function shot(page: Page): Promise<string | null> {
  return screenshotDataUrl(page).catch(() => null);
}
