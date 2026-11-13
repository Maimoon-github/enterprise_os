/**
 * Places calls from AgentSDR through the rep's WhatsApp Web tab, and carries
 * their recordings and outcomes back to AgentSDR.
 *
 * The call itself is dialed and recorded inside web.whatsapp.com (wa-agent,
 * wa-hook); this worker opens the chat, keeps the call's state across its
 * steps (storage.session, which survives this worker being suspended),
 * relays the call's phase to the AgentSDR tab, and uploads the recording.
 */

import type {
  AgentTokenRequest,
  AgentTokenResponse,
  FinishCallRequest,
  RecorderBridgeRequest,
  RecorderCallPhase,
  RecorderCallRequest,
} from "../../../src/lib/calls/contract";
import { digitsOnly } from "../../../src/lib/calls/digits";
import {
  WA_HEARD_AUDIO_PORT,
  WA_RECORDING_PORT,
  type ActiveCall,
  type AgentCommand,
  type AgentTokenResult,
  type BackgroundMessage,
  type BridgeCommand,
  type AgentOutcomeReport,
  type BridgeResult,
  type ProbeResult,
  type RecentCall,
  type WaCall,
  type WaHeardAudioPortMessage,
  type WaRecordingPortMessage,
  type WaScanResult,
  type WaSendOutcome,
} from "./messages";
import type { StationIncomingCall, StationInboundSource, StationInboundTake, StationSendResult } from "../../../src/lib/calls/stationContract";
import { addIncoming, asIncomingCall, endIncoming, takeIncoming, type IncomingEntry } from "./incoming";
import { mergeInbound, type InboundBuffer } from "./inbound";
import { allowedOrigins, customOrigins, isCustomOriginsChange, originPattern } from "./origins";
import { callApi, getCallStatus, uploadRecording } from "./upload";

const ACTIVE_CALL_KEY = "activeCall";
/** The toolbar icon's tooltip between calls. */
const IDLE_TITLE = "AgentSDR Call Recorder";
const RECENT_CALLS_KEY = "recentCalls";
/** How long the WhatsApp tab can keep asking about a finished call. */
const RECENT_CALL_TTL_MS = 2 * 60 * 60 * 1000;
/** A call not recorded within this long is treated as abandoned. */
const ACTIVE_CALL_TTL_MS = 30 * 60 * 1000;
/**
 * WhatsApp stays in front until its call screen says "Ringing": hidden
 * sooner, Chrome throttles the tab and WhatsApp's call set-up slowed from
 * about a second to 4.4 s (measured 29 Sep 2026). This is the longest it
 * waits for "Ringing" before switching back anyway.
 */
const RETURN_FALLBACK_MS = 10_000;
/** Calls placed by the extension whose rep has not been switched back yet. */
const awaitingReturn = new Set<string>();
/** wa-agent's own in-place attempt gives up at 6 s; this only catches a hang. */
// --- call timing ---------------------------------------------------------------
// Each step of a call, in ms after the rep's click, printed to the AgentSDR
// tab's console (and this worker's) once the call rings or settles — to see
// where the time between "Call" and ringing goes.

type Timing = { t0: number; steps: { step: string; ms: number }[] };
const timings = new Map<string, Timing>();
const TIMING_REPORT_PHASES = new Set(["on-call", "not-answered", "not-on-whatsapp", "error", "manual-dial"]);

function startTiming(callId: string, clickedAt: number | undefined): void {
  const now = Date.now();
  timings.set(callId, { t0: clickedAt ?? now, steps: [] });
  if (clickedAt !== undefined) trace(callId, "AgentSDR: Call clicked", clickedAt);
  trace(callId, "Extension: got the call (AgentSDR had created it on the server)", now);
}

/**
 * Every step, also kept for the call worker to collect (station.drainLog):
 * CloakBrowser hides console messages from automation (23 Oct 2026), so a
 * cloud call's log has to be fetched rather than watched.
 */
const stationLog: string[] = [];
const STATION_LOG_MAX = 500;
/**
 * Kept in session storage too: Chrome restarts this service worker when it
 * likes, and a cloud call's log came back empty (23 Oct 2026). The restarted
 * worker has also lost `timings`, so a step is logged even without one.
 */
const STATION_LOG_KEY = "stationLog";
let stationLogFlush: ReturnType<typeof setTimeout> | null = null;

function keepStationLogLine(line: string): void {
  stationLog.push(line);
  if (stationLogFlush) return;
  stationLogFlush = setTimeout(() => void flushStationLog(), 300);
}

async function flushStationLog(): Promise<void> {
  stationLogFlush = null;
  const lines = stationLog.splice(0, stationLog.length);
  if (lines.length === 0) return;
  const stored = ((await chrome.storage.session.get(STATION_LOG_KEY))[STATION_LOG_KEY] as string[] | undefined) ?? [];
  await chrome.storage.session.set({ [STATION_LOG_KEY]: [...stored, ...lines].slice(-STATION_LOG_MAX) });
}

function trace(callId: string, step: string, at = Date.now()): void {
  const timing = timings.get(callId);
  const clock = new Date(at).toISOString().slice(11, 23);
  if (!timing) {
    keepStationLogLine(`${callId.slice(0, 8)} ${clock} ${step}`);
    return;
  }
  const ms = at - timing.t0;
  timing.steps.push({ step, ms });
  const line = `${callId.slice(0, 8)} ${clock} +${ms}ms ${step}`;
  console.log(`[recorder] ${line}`);
  keepStationLogLine(line);
}

async function reportTiming(callId: string): Promise<void> {
  const timing = timings.get(callId);
  const call = await recentCall(callId);
  if (!timing) return;
  console.table(timing.steps);
  if (call?.appTabId === undefined) return;
  const report: BridgeCommand = { target: "bridge", type: "call:timing", callId, steps: timing.steps };
  await chrome.tabs.sendMessage(call.appTabId, report).catch(() => {});
}
const OPEN_IN_PLACE_TIMEOUT_MS = 9_000;

chrome.runtime.onInstalled.addListener(() => void syncCustomBridges().then(refreshBridges));
chrome.runtime.onStartup.addListener(() => void syncCustomBridges());
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "sync" && isCustomOriginsChange(changes)) void syncCustomBridges().then(refreshBridges);
});
chrome.permissions.onAdded.addListener(() => void syncCustomBridges().then(refreshBridges));
chrome.permissions.onRemoved.addListener(() => void syncCustomBridges());

const CUSTOM_BRIDGE_ID = "bridge-custom-origins";

/**
 * The bridge for AgentSDR origins added on the Options page (a self-hosted
 * AgentSDR). Manifest content scripts cover only the built-in origins, so
 * the added ones get the same bridge registered at runtime — for those whose
 * host permission is still granted.
 */
async function syncCustomBridges(): Promise<void> {
  const granted: string[] = [];
  for (const origin of await customOrigins()) {
    if (await chrome.permissions.contains({ origins: [originPattern(origin)] })) granted.push(origin);
  }
  const existing = await chrome.scripting.getRegisteredContentScripts({ ids: [CUSTOM_BRIDGE_ID] });
  if (existing.length) await chrome.scripting.unregisterContentScripts({ ids: [CUSTOM_BRIDGE_ID] });
  if (!granted.length) return;
  await chrome.scripting
    .registerContentScripts([
      {
        id: CUSTOM_BRIDGE_ID,
        matches: granted.map(originPattern),
        js: ["bridge.js"],
        runAt: "document_start",
        persistAcrossSessions: true,
      },
    ])
    .catch((error: unknown) => console.warn("[recorder] could not register the bridge for added origins", error));
}

/**
 * Chrome only injects manifest content scripts into pages loaded after the
 * extension was, so AgentSDR tabs already open at install or update would be
 * left with no bridge, or an orphaned one. Give them a fresh copy.
 */
async function refreshBridges(): Promise<void> {
  const tabs = await chrome.tabs.query({ url: (await allowedOrigins()).map(originPattern) });
  for (const tab of tabs) {
    if (tab.id === undefined) continue;
    await chrome.scripting
      .executeScript({ target: { tabId: tab.id }, files: ["bridge.js"] })
      .catch((error: unknown) => console.warn("[recorder] could not refresh the bridge in tab", tab.id, error));
  }
}

chrome.runtime.onMessage.addListener((message: BackgroundMessage, sender, sendResponse) => {
  if (message.target !== "background") return;

  switch (message.type) {
    case "bridge":
      void handleBridge(message.request, sender).then(sendResponse);
      return true; // answers asynchronously
    case "wa:hello":
      void callForTab(sender.tab?.id).then(sendResponse);
      return true;
    case "wa:dialed":
      void updateActiveCall(message.callId, { dialedAt: Date.now() });
      // Back to AgentSDR once the call is placed; WhatsApp carries it on in
      // its picture-in-picture window. Not when the rep still has to press
      // Voice call themselves.
      if (message.pressed) {
        awaitingReturn.add(message.callId);
        setTimeout(() => returnToAgentSdr(message.callId, "no \"Ringing\" within 10 s"), RETURN_FALLBACK_MS);
      }
      break;
    case "wa:answered":
      void onAnswered(message.callId, message.answeredAt);
      break;
    case "wa:not-answered":
      void finishActiveCall(message.callId, {
        outcome: "no_recording",
        startedAt: new Date(message.dialedAt).toISOString(),
        endedAt: new Date(message.endedAt).toISOString(),
      });
      break;
    case "wa:not-on-whatsapp":
      // The error's "isn't on WhatsApp" is what marks the lead Not on WhatsApp.
      void finishActiveCall(message.callId, {
        outcome: "failed",
        error: message.noCallButton
          ? "This number isn't on WhatsApp for calls (its chat has no Voice call button, as with a business number)"
          : "This number isn't on WhatsApp",
      });
      break;
    case "wa:recording-failed":
      void finishActiveCall(message.callId, { outcome: "failed", error: `Recording failed: ${message.error}` });
      break;
    case "wa:status":
      void statusFor(message.callId).then(sendResponse);
      return true;
    case "wa:focus-app":
      // The automatic return at the end of a call is skipped when the rep
      // was already switched back when it rang — they may have gone to
      // WhatsApp on purpose since. The rep's own "Back" always works.
      if (!(message.auto && returnedToAgentSdr.has(message.callId))) void focusApp(message.callId);
      break;
    case "wa:call-shown":
      // The call screen is up: back to AgentSDR now rather than at "Ringing…",
      // which WhatsApp does not always show.
      returnToAgentSdr(message.callId, "WhatsApp shows the call screen");
      break;
    case "wa:phase":
      trace(message.callId, `phase: ${message.phase.kind}`);
      if (message.phase.kind !== "calling" && message.phase.kind !== "ringing" && message.phase.kind !== "opening") {
        returnToAgentSdr(message.callId, `the call moved on (${message.phase.kind})`);
      }
      void forwardPhase(message.callId, message.phase);
      if (TIMING_REPORT_PHASES.has(message.phase.kind)) void reportTiming(message.callId);
      break;
    case "wa:agent-token":
      void agentToken(message.callId).then(sendResponse);
      return true;
    case "wa:agent-outcome":
      void agentOutcome(message.callId, message.outcome).then(sendResponse);
      return true;
    case "wa:trace":
      trace(message.callId, message.step);
      if (/^WhatsApp shows "Ringing/i.test(message.step)) {
        returnToAgentSdr(message.callId, "WhatsApp is ringing");
        void reportTiming(message.callId);
      }
      break;
    // Station messaging (see "station messaging" below):
    case "wa:messaging-hello":
      void messagingEnabled().then((enabled) => sendResponse({ enabled }));
      return true;
    case "wa:messaging-source":
      void setHookCapability(message.capability);
      break;
    case "wa:inbound":
      void bufferInbound(message.messages);
      break;
    case "wa:msg-log":
      msgLog(message.step);
      break;
    // Incoming calls (see "incoming calls" below):
    case "wa:incoming-call":
      void noteIncomingCall(message.call, sender.tab?.id ?? null);
      break;
    case "wa:incoming-ended":
      void noteIncomingEnded(message.waCallId);
      break;
  }
});

/**
 * A request from an AgentSDR page, relayed by the bridge content script. The
 * sender's origin is checked again here rather than trusted.
 */
async function handleBridge(
  request: RecorderBridgeRequest,
  sender: chrome.runtime.MessageSender,
): Promise<BridgeResult> {
  const senderOrigin = sender.origin ?? (sender.url ? new URL(sender.url).origin : null);
  const origins = await allowedOrigins();
  if (!senderOrigin || !origins.includes(senderOrigin)) {
    return { ok: false, error: `Requests are only accepted from ${origins.join(" or ")}. Add your AgentSDR address in the extension's Options.` };
  }
  if (request.type === "call:end") return endCall(request.callId);
  if (request.type === "recorder:update") {
    // The Update page downloads the build from the AgentSDR that asked for it.
    await chrome.tabs.create({ url: chrome.runtime.getURL(`update.html?from=${encodeURIComponent(senderOrigin)}`) });
    return { ok: true };
  }
  const digits = digitsOnly(request.phone);
  if (digits.length < 7) return { ok: false, error: `"${request.phone}" is not a dialable number` };

  if (request.type === "message:open") {
    // The tab reloads for the message; a call still waiting to be dialed
    // there must not be dialed by that reload.
    const pending = await getActiveCall();
    if (pending && !pending.dialedAt) await updateActiveCall(pending.callId, { dialedAt: Date.now() });
    // Typed in, not sent: the rep reads it and presses Enter themselves, so
    // WhatsApp comes to the front. Answered before the chat opens — see startCall.
    void openChat(digits, { text: request.text, focus: true }).catch((error) => console.warn("[recorder] could not open the chat", error));
    return { ok: true };
  }
  if (request.apiBase !== senderOrigin) {
    return { ok: false, error: "A call must report back to the page that placed it" };
  }
  return startCall(request, digits, sender.tab?.id);
}

/**
 * A call placed from the app: remember it, and open the chat. wa-agent in
 * that tab then dials it and wa-hook records it (see wa-hook.ts).
 */
async function startCall(
  request: RecorderCallRequest,
  digits: string,
  appTabId: number | undefined,
  station = false,
): Promise<BridgeResult> {
  const refused = await settlePreviousCall();
  if (refused) return refused;

  // A rep talking through the station is station mode only, and has no agent.
  const remoteRep = station && request.remoteRep === true;
  const call: ActiveCall = {
    callId: request.callId,
    recorderToken: request.recorderToken,
    apiBase: request.apiBase,
    phone: request.phone,
    requestedAt: Date.now(),
    lead: request.lead,
    appTabId,
    agent: remoteRep ? null : requestAgent(request),
    remoteRep,
    station,
  };
  await rememberCall(call);
  startTiming(call.callId, request.clickedAt);
  // Stored before the chat opens, so wa-agent's reports (and, after a
  // reload, its hello) find it. The tab id is merged in afterwards rather
  // than written over, since wa-agent may already have reported dialing.
  await setActiveCall(call);
  // The page is answered now, not after the chat opens: an in-place open can
  // take several seconds to confirm, and the page gives up on a silent
  // extension after 5 s and marks the call failed — after which the app
  // refuses its recording. From here on the card, not the page, reports.
  void openChat(digits, { call: waCall(call), focus: true })
    .then((tabId) => updateActiveCall(call.callId, { tabId }))
    .catch((error) => console.warn("[recorder] could not open the chat", error));
  return { ok: true };
}

/** The AI agent a call request asks for, trimmed; null when it has no brief. */
function requestAgent(request: Pick<RecorderCallRequest, "agent">): ActiveCall["agent"] {
  return request.agent?.brief?.trim()
    ? {
        brief: request.agent.brief.trim(),
        name: request.agent.name?.trim() || null,
        voice: request.agent.voice?.trim() || null,
      }
    : null;
}

/**
 * Before a new call: the call before it is closed out, or — still being
 * recorded — the reason the new one is refused.
 */
async function settlePreviousCall(): Promise<BridgeResult | null> {
  const previous = await getActiveCall();
  if (previous?.answeredAt) {
    if (await stillBusy(previous)) {
      return { ok: false, error: "The last call is still being recorded — hang it up first" };
    }
    // The WhatsApp tab no longer has that call — reloaded or closed during
    // it, or the extension was. Its end will never be reported, and without
    // this it would block calling until Chrome restarts.
    await callApi(previous, "finish", {
      outcome: "failed",
      error: "The call was interrupted: WhatsApp or the extension reloaded during it, so the recording was lost",
    }).catch(() => {});
    await clearActiveCall(previous.callId);
  }
  // A call that was opened but never recorded is over; say so rather than
  // leaving it pending in the app.
  if (previous) await callApi(previous, "finish", { outcome: "no_recording" }).catch(() => {});
  return null;
}

/**
 * Opens the chat in the rep's WhatsApp Web tab — in place when that tab is
 * already loaded (about a second), otherwise by loading it at
 * /send?phone=… (a full WhatsApp Web start-up). Returns the tab's id.
 *
 * WhatsApp comes to the front to open the chat: in a background tab it does
 * not re-render the chat header in time for openInPlace to confirm the chat,
 * so the call would fall back to a slow reload (seen 29 Sep 2026). For a call
 * it is only for a moment — once Voice call is pressed the rep is switched
 * back to AgentSDR (the wa:dialed handler), WhatsApp moves the call into its
 * picture-in-picture window, and the call's phase is pushed to AgentSDR.
 */
async function openChat(
  digits: string,
  options: { call?: WaCall; text?: string; focus: boolean },
): Promise<number | undefined> {
  const url = `https://web.whatsapp.com/send?phone=${digits}${options.text ? `&text=${encodeURIComponent(options.text)}` : ""}`;
  const callId = options.call?.callId;
  const note = (step: string) => {
    if (callId) trace(callId, step);
  };
  const [existing] = await chrome.tabs.query({ url: "https://web.whatsapp.com/*" });
  if (existing?.id === undefined) {
    note("Extension: no WhatsApp tab open — opening one (full WhatsApp start-up)");
    return (await chrome.tabs.create({ url })).id;
  }

  if (options.focus) await focusTab(existing);
  note("Extension: WhatsApp tab in front; opening the chat in place");
  if (await openInPlace(existing.id, digits, options)) {
    note("Extension: chat opened in place");
    return existing.id;
  }
  note("Extension: in-place open failed — reloading WhatsApp (full start-up)");
  // A fresh load has had no click from the rep yet, so Chrome may hold its
  // audio back; bring it forward for this one.
  await chrome.tabs.update(existing.id, { url });
  await focusTab(existing);
  return existing.id;
}

async function focusTab(tab: chrome.tabs.Tab): Promise<void> {
  if (tab.id === undefined) return;
  await chrome.tabs.update(tab.id, { active: true });
  await chrome.windows.update(tab.windowId, { focused: true });
}

/** Switches the rep back to AgentSDR once per call, when the call has got going. */
/** Calls whose rep was switched back to AgentSDR when the call rang. */
const returnedToAgentSdr = new Set<string>();

function returnToAgentSdr(callId: string, why: string): void {
  if (!awaitingReturn.delete(callId)) return;
  returnedToAgentSdr.add(callId);
  void focusApp(callId).then(() => trace(callId, `Extension: switched back to AgentSDR (${why})`));
}

/** AgentSDR's End call: pressed in the WhatsApp tab holding the call. */
async function endCall(callId: string): Promise<BridgeResult> {
  const call = await getActiveCall();
  // Already closed out — hung up in WhatsApp and reported: nothing to end.
  if (!call || call.callId !== callId) return { ok: true };
  // The call's own tab when known; otherwise the rep's WhatsApp tab, which is
  // where calls are placed.
  const tabId = call.tabId ?? (await chrome.tabs.query({ url: "https://web.whatsapp.com/*" }))[0]?.id;
  if (tabId === undefined) return { ok: false, error: "No WhatsApp Web tab is open" };
  const command: AgentCommand = { target: "wa-agent", type: "end", callId };
  try {
    return (await chrome.tabs.sendMessage<AgentCommand, BridgeResult>(tabId, command)) ?? {
      ok: false,
      error: "WhatsApp didn't answer",
    };
  } catch {
    return { ok: false, error: "The WhatsApp tab can't be reached — reload it" };
  }
}

/** Sends a call's phase to the AgentSDR tab that placed it. */
async function forwardPhase(callId: string, phase: RecorderCallPhase): Promise<void> {
  const call = await recentCall(callId);
  if (call?.station) {
    // No AgentSDR tab in a cloud browser: the rep's page reads it from the server.
    await callApi(call, "phase", { phase }).catch(() => {});
    return;
  }
  if (call?.appTabId === undefined) return;
  const update: BridgeCommand = { target: "bridge", type: "call:update", callId, phase };
  await chrome.tabs.sendMessage(call.appTabId, update).catch(() => {
    // The AgentSDR tab was closed or navigated away; nothing to update.
  });
}

/**
 * Asks wa-agent in a loaded tab to open the chat itself. False when there is
 * no live wa-agent there (the tab predates this extension build, or is still
 * loading) or it could not confirm the chat — the caller then reloads.
 */
async function openInPlace(tabId: number, digits: string, options: { call?: WaCall; text?: string }): Promise<boolean> {
  const command: AgentCommand = {
    target: "wa-agent",
    type: "open",
    phone: digits,
    text: options.text ?? null,
    call: options.call ?? null,
  };
  try {
    const result = await Promise.race([
      chrome.tabs.sendMessage<AgentCommand, BridgeResult>(tabId, command),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), OPEN_IN_PLACE_TIMEOUT_MS)),
    ]);
    return result?.ok === true;
  } catch {
    return false;
  }
}

/** wa-agent's hello: the call to place in its tab, if one was just opened there. */
/**
 * What wa-agent is told about a call — never the agent's brief, and never its
 * token except on a rep call, whose audio relay wa-agent calls with it (see
 * WaCall.repRelay).
 */
function waCall(call: ActiveCall): WaCall {
  return {
    callId: call.callId,
    phone: call.phone,
    lead: call.lead ?? null,
    agent: Boolean(call.agent),
    station: Boolean(call.station),
    repRelay: call.station && call.remoteRep ? { apiBase: call.apiBase, recorderToken: call.recorderToken } : null,
  };
}

/** Asks AgentSDR for the AI agent's Gemini Live token, with the call's own bearer token. */
async function agentToken(callId: string): Promise<AgentTokenResult> {
  const call = await getActiveCall();
  if (!call || call.callId !== callId || !call.agent) return { ok: false, error: "This call has no AI agent" };
  try {
    const request: AgentTokenRequest = {
      brief: call.agent.brief,
      lead: call.lead ?? null,
      name: call.agent.name ?? null,
      voice: call.agent.voice ?? null,
    };
    const token = await callApi<AgentTokenResponse>(call, "agent-token", request);
    trace(callId, "AI agent: token minted");
    return { ok: true, ...token };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}

/** The AI agent's record_outcome report: POSTed with the call's bearer token (the call may already be over). */
async function agentOutcome(callId: string, outcome: AgentOutcomeReport): Promise<BridgeResult> {
  const active = await getActiveCall();
  const call = active?.callId === callId ? active : await recentCall(callId);
  if (!call) return { ok: false, error: "This call is no longer known to the extension" };
  try {
    await callApi(call, "outcome", outcome);
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}

async function callForTab(tabId: number | undefined): Promise<WaCall | null> {
  const call = await getActiveCall();
  // An answered incoming call is never handed to a (re)loaded tab: wa-agent would dial out.
  if (!call || tabId === undefined || call.dialedAt || call.inbound) return null;
  // The tab id is recorded right after navigation starts; a hello that races
  // it (or comes from the only WhatsApp tab) is still this call's.
  if (call.tabId !== undefined && call.tabId !== tabId) return null;
  if (Date.now() - call.requestedAt >= ACTIVE_CALL_TTL_MS) return null;
  return waCall(call);
}

/**
 * Calls stay known here for a while after they end, so the call card can
 * show the transcript arriving and "Back to AgentSDR" can find its tab.
 */
async function rememberCall(call: ActiveCall): Promise<void> {
  const stored = await chrome.storage.session.get(RECENT_CALLS_KEY);
  const recent = (stored[RECENT_CALLS_KEY] as Record<string, RecentCall> | undefined) ?? {};
  const now = Date.now();
  for (const [id, entry] of Object.entries(recent)) if (now - entry.endedAt > RECENT_CALL_TTL_MS) delete recent[id];
  recent[call.callId] = {
    callId: call.callId,
    recorderToken: call.recorderToken,
    apiBase: call.apiBase,
    appTabId: call.appTabId,
    station: call.station,
    endedAt: now,
  };
  await chrome.storage.session.set({ [RECENT_CALLS_KEY]: recent });
}

async function recentCall(callId: string): Promise<RecentCall | null> {
  const stored = await chrome.storage.session.get(RECENT_CALLS_KEY);
  return (stored[RECENT_CALLS_KEY] as Record<string, RecentCall> | undefined)?.[callId] ?? null;
}

async function statusFor(callId: string) {
  const call = await recentCall(callId);
  return call ? getCallStatus(call).catch(() => null) : null;
}

/** "Back to AgentSDR": the tab the call came from, else any AgentSDR tab, else a new one. */
async function focusApp(callId: string): Promise<void> {
  const call = await recentCall(callId);
  // A cloud browser has no rep to bring back to AgentSDR.
  if (call?.station) return;
  const tab =
    (call?.appTabId !== undefined ? await chrome.tabs.get(call.appTabId).catch(() => null) : null) ??
    (await chrome.tabs.query({ url: (await allowedOrigins()).map(originPattern) }))[0] ??
    null;
  if (tab?.id !== undefined) {
    await chrome.tabs.update(tab.id, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
  } else if (call) {
    await chrome.tabs.create({ url: `${call.apiBase}/calling` });
  }
}

async function onAnswered(callId: string, answeredAt: number): Promise<void> {
  const call = await updateActiveCall(callId, { answeredAt });
  if (!call) return;
  await setBadge("REC", "#d92d20", "Recording this call");
  await callApi(call, "started", { startedAt: new Date(answeredAt).toISOString() }).catch((error) =>
    console.warn("[recorder] could not mark the call started", error),
  );
}

/** Reports the active call's end without a recording, and forgets it. */
/**
 * Reports a call's end without a recording. Usually the active call; an
 * earlier call whose end arrives late (see wa-agent's finishOtherCall) is
 * reported through the details kept for recent calls.
 */
async function finishActiveCall(callId: string, finish: FinishCallRequest): Promise<void> {
  const active = await getActiveCall();
  const call = active?.callId === callId ? active : await recentCall(callId);
  if (!call) return;
  if (call === active) {
    await clearActiveCall(callId);
    await setBadge("", "#000000", IDLE_TITLE);
  }
  await callApi(call, "finish", finish).catch((error) => console.warn("[recorder] could not report the call", error));
}

/**
 * Whether the WhatsApp tab holding `call` is still recording, finishing off
 * or uploading it. A tab that can't be reached has lost it.
 */
async function stillBusy(call: ActiveCall): Promise<boolean> {
  if (call.tabId === undefined) return false;
  try {
    const result = await Promise.race([
      chrome.tabs.sendMessage<AgentCommand, ProbeResult>(call.tabId, { target: "wa-agent", type: "probe" }),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 2_000)),
    ]);
    return result?.busyCallIds.includes(call.callId) ?? false;
  } catch {
    return false;
  }
}

// wa-agent streams a finished recording here: runtime messages are JSON-only,
// so the file crosses as base64 chunks and is uploaded from this worker,
// whose host permissions spare it CORS.
chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== WA_HEARD_AUDIO_PORT) return;
  let callId: string | null = null;
  const parts: Uint8Array<ArrayBuffer>[] = [];
  port.onMessage.addListener((message: WaHeardAudioPortMessage) => {
    if (message.type === "meta") callId = message.callId;
    else if (message.type === "chunk") parts.push(fromBase64(message.data));
    else if (callId) void uploadHeardAudio(port, callId, parts);
  });
});

/** The heard-audio test option: POSTs the WAV of what the AI agent heard, with the call's bearer token. */
async function uploadHeardAudio(port: chrome.runtime.Port, callId: string, parts: Uint8Array<ArrayBuffer>[]): Promise<void> {
  const active = await getActiveCall();
  const call = active?.callId === callId ? active : await recentCall(callId);
  if (!call) {
    port.postMessage({ ok: false, error: "This call is no longer known to the extension" } satisfies BridgeResult);
    return;
  }
  try {
    const response = await fetch(`${call.apiBase}/api/call-recorder/calls/${callId}/heard-audio`, {
      method: "POST",
      headers: { Authorization: `Bearer ${call.recorderToken}`, "Content-Type": "audio/wav" },
      body: new Blob(parts, { type: "audio/wav" }),
    });
    if (!response.ok) {
      const detail = (await response.json().catch(() => null)) as { error?: string } | null;
      throw new Error(detail?.error ?? `heard-audio answered ${response.status}`);
    }
    port.postMessage({ ok: true } satisfies BridgeResult);
  } catch (error) {
    port.postMessage({ ok: false, error: error instanceof Error ? error.message : String(error) } satisfies BridgeResult);
  }
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== WA_RECORDING_PORT) return;
  let meta: Extract<WaRecordingPortMessage, { type: "meta" }> | null = null;
  const parts: Uint8Array<ArrayBuffer>[] = [];
  port.onMessage.addListener((message: WaRecordingPortMessage) => {
    if (message.type === "meta") meta = message;
    else if (message.type === "chunk") parts.push(fromBase64(message.data));
    else if (meta) void receiveRecording(port, meta, parts);
  });
});

async function receiveRecording(
  port: chrome.runtime.Port,
  meta: Extract<WaRecordingPortMessage, { type: "meta" }>,
  parts: Uint8Array<ArrayBuffer>[],
): Promise<void> {
  const active = await getActiveCall();
  // An earlier call's recording can arrive after a new call started (see
  // wa-agent's finishOtherCall): upload it with the details kept for it.
  const call = active?.callId === meta.callId ? active : await recentCall(meta.callId);
  if (!call) {
    port.postMessage({ ok: false, error: "This call is no longer known to the extension" } satisfies BridgeResult);
    return;
  }
  if (call === active) {
    await clearActiveCall(meta.callId);
    await setBadge("", "#000000", IDLE_TITLE);
  }
  try {
    await uploadRecording(call, new Blob(parts, { type: meta.mimeType }), meta.startedAt, meta.endedAt, meta.answeredAt);
    port.postMessage({ ok: true } satisfies BridgeResult);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await callApi(call, "finish", { outcome: "failed", error: `Upload failed: ${message}` }).catch(() => {});
    port.postMessage({ ok: false, error: message } satisfies BridgeResult);
  }
}

function fromBase64(data: string): Uint8Array<ArrayBuffer> {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function getActiveCall(): Promise<ActiveCall | null> {
  const stored = await chrome.storage.session.get(ACTIVE_CALL_KEY);
  return (stored[ACTIVE_CALL_KEY] as ActiveCall | undefined) ?? null;
}

// Writes to the active call run one at a time. Each update reads the stored
// call, changes a field and writes it back; two in flight at once (the tab id
// after the chat opens, "dialed" right after Voice call) each wrote back the
// copy they read, and one erased the other — the tab id went missing, and
// End call could not find the call's tab. A queue, not a lock: none of these
// may wait on another from inside it.
let activeCallWrites: Promise<unknown> = Promise.resolve();

function serialized<T>(write: () => Promise<T>): Promise<T> {
  const next = activeCallWrites.then(write, write);
  activeCallWrites = next.catch(() => {});
  return next;
}

function setActiveCall(call: ActiveCall): Promise<void> {
  return serialized(() => chrome.storage.session.set({ [ACTIVE_CALL_KEY]: call }));
}

/** Forgets the active call — only if it is still `callId`, not a newer call. */
function clearActiveCall(callId: string): Promise<void> {
  return serialized(async () => {
    const call = await getActiveCall();
    if (call?.callId === callId) await chrome.storage.session.remove(ACTIVE_CALL_KEY);
  });
}

function updateActiveCall(callId: string, patch: Partial<ActiveCall>): Promise<ActiveCall | null> {
  return serialized(async () => {
    const call = await getActiveCall();
    if (!call || call.callId !== callId) return null;
    const next = { ...call, ...patch };
    await chrome.storage.session.set({ [ACTIVE_CALL_KEY]: next });
    return next;
  });
}

async function setBadge(text: string, color: string, title: string): Promise<void> {
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color });
  await chrome.action.setTitle({ title });
}

// --- station mode (cloud calling) ---------------------------------------------

/** What the call worker passes to start a call: a bridge call request without the page's envelope. */
type StationCallRequest = Omit<RecorderCallRequest, "source" | "type" | "requestId">;

/**
 * A calling station: this browser runs in the cloud and AgentSDR's call
 * worker drives it over CDP (Playwright's serviceWorker.evaluate), so calls
 * arrive here rather than through an AgentSDR page's bridge. Everything after
 * startCall is the path a rep's call takes. Only whoever controls the browser
 * can reach this, so there is no origin check — the call's own bearer token
 * still authorizes everything it reports.
 */
const station = {
  /** With `remoteRep: true` (0.24.0+), the rep talks from their AgentSDR tab instead of the agent, through AgentSDR's relay — see rep-relay.ts. */
  async startCall(request: StationCallRequest): Promise<BridgeResult> {
    const digits = digitsOnly(request.phone);
    if (digits.length < 7) return { ok: false, error: `"${request.phone}" is not a dialable number` };
    const call: RecorderCallRequest = { ...request, source: "agentsdr-app", type: "call:start", requestId: crypto.randomUUID() };
    return startCall(call, digits, undefined, true);
  },
  endCall,
  /** The call this browser is on, if any — for the worker's watch. */
  async activeCall(): Promise<Pick<ActiveCall, "callId" | "dialedAt" | "answeredAt"> | null> {
    const call = await getActiveCall();
    return call ? { callId: call.callId, dialedAt: call.dialedAt, answeredAt: call.answeredAt } : null;
  },
  /** The steps logged since the last call, oldest first — the worker's view into the call. */
  async drainLog(): Promise<string[]> {
    await flushStationLog();
    const lines = ((await chrome.storage.session.get(STATION_LOG_KEY))[STATION_LOG_KEY] as string[] | undefined) ?? [];
    await chrome.storage.session.remove(STATION_LOG_KEY);
    return lines;
  },
  version: chrome.runtime.getManifest().version,
  /** Sends a WhatsApp text from this number to `phone` (E.164); see "station messaging" below. */
  sendMessage: (request: { phone: string; text: string }): Promise<StationSendResult> => sendStationMessage(request),
  /** The messages this number saw since the last take (inbound, and outbound from the phone or sendMessage); clears them. */
  takeInbound: (): Promise<StationInboundTake> => takeStationInbound(),
  /** The WhatsApp calls ringing on this number since the last take, young enough to answer (0.22.0+); see "incoming calls" below. */
  takeIncomingCalls: (): Promise<StationIncomingCall[]> => takeIncomingCalls(),
  /** Answers the ringing call `waCallId` as AgentSDR's call `callId`: the agent talks, the call is recorded (0.22.0+). */
  answerCall: (request: StationCallRequest & { waCallId: string }): Promise<BridgeResult> => answerIncomingCall(request),
};

(globalThis as unknown as { agentsdrStation?: typeof station }).agentsdrStation = station;

// =============================================================================
// --- station messaging (calling stations only) --------------------------------
// =============================================================================
//
// A calling station also sends and reads WhatsApp messages for AgentSDR: the
// call worker calls agentsdrStation.sendMessage / takeInbound. Nothing here
// runs on a rep's laptop: reading messages is enabled only once one of those
// is called (MESSAGING_ENABLED_KEY), and wa-agent asks for that flag on every
// load before it lets wa-hook read WhatsApp's message store.
//
// Messages never interrupt a call: a send is refused (retryable) while a call
// is being placed, rings, is on or is being finished off, and the tab is never
// reloaded for a message then.

const MESSAGING_ENABLED_KEY = "messagingEnabled";
/** "store" | "none": whether wa-hook's message-store listener is attached, as wa-agent last reported. */
const MESSAGING_HOOK_SOURCE_KEY = "messagingHookSource";
/** The messages waiting for the next take, and the key ids already buffered (InboundBuffer). */
const INBOUND_BUFFER_KEY = "inboundBuffer";
const LAST_DOM_SCAN_KEY = "lastDomScan";
/** One send, from the worker's call to its answer. */
const SEND_TIMEOUT_MS = 30_000;
/** The DOM fallback opens chats, so it runs at most this often. */
const DOM_SCAN_EVERY_MS = 10_000;
const DOM_SCAN_TIMEOUT_MS = 25_000;
/** A call dialed this long ago and never answered is not ringing any more (its end was missed). */
const RINGING_AT_MOST_MS = 3 * 60 * 1000;
/** A call requested this long ago and never dialed is not being placed any more. */
const PLACING_AT_MOST_MS = 2 * 60 * 1000;
const WHATSAPP_TABS = "https://web.whatsapp.com/*";

function msgLog(step: string): void {
  const line = `msg ${new Date().toISOString().slice(11, 23)} ${step}`;
  console.log(`[recorder] ${line}`);
  keepStationLogLine(line);
}

async function messagingEnabled(): Promise<boolean> {
  return (await chrome.storage.session.get(MESSAGING_ENABLED_KEY))[MESSAGING_ENABLED_KEY] === true;
}

/** Turns messaging on for this browser (station mode) and tells every WhatsApp tab. Idempotent. */
async function enableMessaging(): Promise<void> {
  if (!(await messagingEnabled())) {
    await chrome.storage.session.set({ [MESSAGING_ENABLED_KEY]: true });
    msgLog("messaging enabled on this station");
  }
  const command: AgentCommand = { target: "wa-agent", type: "messaging-enable" };
  for (const tab of await chrome.tabs.query({ url: WHATSAPP_TABS })) {
    if (tab.id !== undefined) await chrome.tabs.sendMessage(tab.id, command).catch(() => {});
  }
}

async function setHookCapability(capability: Exclude<StationInboundSource, "dom">): Promise<void> {
  const previous = (await chrome.storage.session.get(MESSAGING_HOOK_SOURCE_KEY))[MESSAGING_HOOK_SOURCE_KEY];
  if (previous === capability) return;
  await chrome.storage.session.set({ [MESSAGING_HOOK_SOURCE_KEY]: capability });
  msgLog(`message source: ${capability === "store" ? "WhatsApp's message store" : "not readable from the store (yet)"}`);
}

async function hookCapability(): Promise<Exclude<StationInboundSource, "dom">> {
  return (await chrome.storage.session.get(MESSAGING_HOOK_SOURCE_KEY))[MESSAGING_HOOK_SOURCE_KEY] === "store" ? "store" : "none";
}

/** Why a message must wait for a call, from the call this worker knows about; null when there is none. */
async function stationCallBusy(): Promise<string | null> {
  const call = await getActiveCall();
  if (!call) return null;
  const now = Date.now();
  if (now - call.requestedAt >= ACTIVE_CALL_TTL_MS) return null;
  const id = call.callId.slice(0, 8);
  if (call.answeredAt) return (await stillBusy(call)) ? `call ${id} is on` : null;
  if (call.dialedAt) return now - call.dialedAt < RINGING_AT_MOST_MS ? `call ${id} is ringing` : null;
  return now - call.requestedAt < PLACING_AT_MOST_MS ? `call ${id} is being placed` : null;
}

type AgentAnswer<T> = { kind: "answer"; result: T } | { kind: "no-receiver" } | { kind: "timeout" };

/** A command to wa-agent in `tabId`. "no-receiver": no wa-agent there (yet); "timeout": it did not answer in time. */
async function askAgent<T>(tabId: number, command: AgentCommand, timeoutMs: number): Promise<AgentAnswer<T>> {
  try {
    const answer = await Promise.race([
      chrome.tabs.sendMessage<AgentCommand, T>(tabId, command).then((result): AgentAnswer<T> => ({ kind: "answer", result })),
      new Promise<AgentAnswer<T>>((resolve) => setTimeout(() => resolve({ kind: "timeout" }), Math.max(timeoutMs, 0))),
    ]);
    return answer.kind === "answer" && answer.result === undefined ? { kind: "no-receiver" } : answer;
  } catch {
    return { kind: "no-receiver" };
  }
}

function isSendOutcome(value: unknown): value is WaSendOutcome {
  if (!value || typeof value !== "object") return false;
  const outcome = value as Record<string, unknown>;
  if (outcome.ok === true) return "providerMessageId" in outcome;
  return outcome.ok === false && typeof outcome.error === "string";
}

async function sendStationMessage(request: { phone: string; text: string }): Promise<StationSendResult> {
  const phone = typeof request?.phone === "string" ? request.phone : "";
  const text = typeof request?.text === "string" ? request.text : "";
  const digits = digitsOnly(phone);
  if (digits.length < 7) return { ok: false, retryable: false, error: `"${phone}" is not a valid WhatsApp number` };
  if (!text.trim()) return { ok: false, retryable: false, error: "The message is empty" };
  await enableMessaging();
  msgLog(`send: to +${digits} (${text.length} characters)`);
  const deadline = Date.now() + SEND_TIMEOUT_MS;
  const timedOut: StationSendResult = {
    ok: false,
    retryable: false,
    error: `No answer from WhatsApp Web within ${SEND_TIMEOUT_MS / 1000} s — the message may have been sent`,
  };
  const result = await Promise.race([
    sendStationMessageNow(digits, text, deadline).catch(
      (error: unknown): StationSendResult => ({ ok: false, retryable: false, error: error instanceof Error ? error.message : String(error) }),
    ),
    new Promise<StationSendResult>((resolve) => setTimeout(() => resolve(timedOut), SEND_TIMEOUT_MS)),
  ]);
  msgLog(result.ok ? `send: done (${result.providerMessageId ?? "no id"})` : `send: not sent (${result.retryable ? "retryable" : "final"}) — ${result.error}`);
  return result;
}

async function sendStationMessageNow(digits: string, text: string, deadline: number): Promise<StationSendResult> {
  const busy = await stationCallBusy();
  if (busy) return { ok: false, retryable: true, error: `Not sent: ${busy}` };
  const [tab] = await chrome.tabs.query({ url: WHATSAPP_TABS });
  if (tab?.id === undefined) return { ok: false, retryable: true, error: "No WhatsApp Web tab is open" };
  if (tab.status !== "complete") return { ok: false, retryable: true, error: "WhatsApp Web is still loading" };

  const command: AgentCommand = { target: "wa-agent", type: "send-message", phone: digits, text, afterReload: false };
  const first = await askAgent<WaSendOutcome>(tab.id, command, deadline - Date.now());
  if (first.kind === "no-receiver") {
    return { ok: false, retryable: true, error: "WhatsApp Web's tab did not answer (still loading, or opened before this extension build)" };
  }
  if (first.kind === "timeout") return { ok: false, retryable: false, error: "WhatsApp Web did not finish the send in time — it may have been sent" };
  if (!isSendOutcome(first.result)) return { ok: false, retryable: false, error: "WhatsApp Web gave an unexpected answer" };
  if (!("reload" in first.result)) return first.result;

  // Not opened in place, and nothing typed: load the tab at the chat — never during a call.
  const busyNow = await stationCallBusy();
  if (busyNow) return { ok: false, retryable: true, error: `The chat could not be opened in place, and ${busyNow} — not reloading WhatsApp` };
  msgLog(`send: ${first.result.error} — reloading WhatsApp Web at the chat`);
  await chrome.tabs.update(tab.id, { url: `https://web.whatsapp.com/send?phone=${digits}` });
  await waitForTabLoad(tab.id, deadline);
  while (Date.now() < deadline - 500) {
    const answer = await askAgent<WaSendOutcome>(tab.id, { ...command, afterReload: true }, deadline - Date.now());
    if (answer.kind === "no-receiver") {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
      continue;
    }
    if (answer.kind === "timeout") return { ok: false, retryable: false, error: "WhatsApp Web did not finish the send in time — it may have been sent" };
    if (!isSendOutcome(answer.result)) return { ok: false, retryable: false, error: "WhatsApp Web gave an unexpected answer" };
    if ("reload" in answer.result) return { ok: false, retryable: true, error: answer.result.error };
    return answer.result;
  }
  return { ok: false, retryable: true, error: "WhatsApp Web did not come back after reloading it at the chat" };
}

/** Waits for the navigation to start (the old page must not answer), then for the new page to finish loading. */
async function waitForTabLoad(tabId: number, deadline: number): Promise<void> {
  const status = async () => (await chrome.tabs.get(tabId).catch(() => null))?.status;
  const started = Date.now();
  while (Date.now() - started < 3_000 && Date.now() < deadline && (await status()) === "complete") {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  while (Date.now() < deadline && (await status()) !== "complete") {
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

// The inbound buffer's writes run one at a time (read, merge, write back), like the active call's.
let inboundWrites: Promise<unknown> = Promise.resolve();

function serializedInbound<T>(write: () => Promise<T>): Promise<T> {
  const next = inboundWrites.then(write, write);
  inboundWrites = next.catch(() => {});
  return next;
}

async function readInboundBuffer(): Promise<InboundBuffer> {
  const stored = (await chrome.storage.session.get(INBOUND_BUFFER_KEY))[INBOUND_BUFFER_KEY] as InboundBuffer | undefined;
  return { messages: stored?.messages ?? [], seen: stored?.seen ?? [] };
}

function bufferInbound(messages: unknown): Promise<void> {
  return serializedInbound(async () => {
    if (!Array.isArray(messages) || !messages.length) return;
    if (!(await messagingEnabled())) {
      msgLog(`inbound: ${messages.length} message(s) dropped — messaging is not enabled in this browser`);
      return;
    }
    const merged = mergeInbound(await readInboundBuffer(), messages.filter((message) => message && typeof message === "object"));
    await chrome.storage.session.set({ [INBOUND_BUFFER_KEY]: { messages: merged.messages, seen: merged.seen } satisfies InboundBuffer });
    msgLog(`inbound: ${merged.added} new message(s) waiting (${merged.messages.length} in all${merged.added < messages.length ? `, ${messages.length - merged.added} already seen` : ""})`);
  });
}

async function takeStationInbound(): Promise<StationInboundTake> {
  await enableMessaging();
  let source: StationInboundSource = await hookCapability();
  if (source !== "store" && (await scanUnreadFromPage())) source = "dom";
  const messages = await serializedInbound(async () => {
    const buffer = await readInboundBuffer();
    await chrome.storage.session.set({ [INBOUND_BUFFER_KEY]: { messages: [], seen: buffer.seen } satisfies InboundBuffer });
    return buffer.messages;
  });
  if (messages.length) msgLog(`inbound: ${messages.length} message(s) taken (source ${source})`);
  return { source, messages };
}

/**
 * The DOM fallback: wa-agent opens the chat list's unread chats and reads
 * them. At most every 10 s, never during a call. True when the page could be
 * read (now, or at the last scan within those 10 s).
 */
async function scanUnreadFromPage(): Promise<boolean> {
  const last = (await chrome.storage.session.get(LAST_DOM_SCAN_KEY))[LAST_DOM_SCAN_KEY] as { at: number; ok: boolean } | undefined;
  if (last && Date.now() - last.at < DOM_SCAN_EVERY_MS) return last.ok;
  const busy = await stationCallBusy();
  if (busy) {
    msgLog(`scan: skipped — ${busy}`);
    return last?.ok ?? false;
  }
  const [tab] = await chrome.tabs.query({ url: WHATSAPP_TABS });
  if (tab?.id === undefined || tab.status !== "complete") return false;
  await chrome.storage.session.set({ [LAST_DOM_SCAN_KEY]: { at: Date.now(), ok: last?.ok ?? false } });
  const answer = await askAgent<WaScanResult>(tab.id, { target: "wa-agent", type: "scan-inbound" }, DOM_SCAN_TIMEOUT_MS);
  if (answer.kind !== "answer") {
    msgLog(`scan: WhatsApp Web ${answer.kind === "timeout" ? "did not finish in time" : "did not answer"}`);
    return false;
  }
  if (!answer.result.ok) {
    msgLog(`scan: ${answer.result.skipped ? "skipped" : "failed"} — ${answer.result.error}`);
    if (answer.result.skipped) return last?.ok ?? false;
    await chrome.storage.session.set({ [LAST_DOM_SCAN_KEY]: { at: Date.now(), ok: false } });
    return false;
  }
  await chrome.storage.session.set({ [LAST_DOM_SCAN_KEY]: { at: Date.now(), ok: true } });
  await bufferInbound(answer.result.messages);
  return true;
}

// =============================================================================
// --- incoming calls (calling stations only) ----------------------------------
// =============================================================================
//
// A lead calling a station back is answered by the AI agent. wa-hook notices
// the call ringing (WhatsApp's call store, or its incoming-call screen) — only
// once station mode enabled messaging, so a rep's own WhatsApp Web never
// answers by itself — and wa-agent passes it here. The call worker takes the
// rings about once a second (takeIncomingCalls), asks AgentSDR whether to
// answer, and if so calls answerCall with the call AgentSDR created for it.
// From then on it is a placed call's path, except that wa-agent presses
// Accept instead of Voice call.

const INCOMING_CALLS_KEY = "incomingCalls";
/** How long wa-agent gets to arm the tab for an answered call. */
const ANSWER_TIMEOUT_MS = 10_000;

// The ring list's writes run one at a time (read, change, write back), like the active call's.
let incomingWrites: Promise<unknown> = Promise.resolve();

function serializedIncoming<T>(write: () => Promise<T>): Promise<T> {
  const next = incomingWrites.then(write, write);
  incomingWrites = next.catch(() => {});
  return next;
}

async function readIncoming(): Promise<IncomingEntry[]> {
  const stored = (await chrome.storage.session.get(INCOMING_CALLS_KEY))[INCOMING_CALLS_KEY] as IncomingEntry[] | undefined;
  return Array.isArray(stored) ? stored : [];
}

function noteIncomingCall(value: unknown, tabId: number | null): Promise<void> {
  return serializedIncoming(async () => {
    const call = asIncomingCall(value);
    if (!call) return;
    if (!(await messagingEnabled())) {
      msgLog("incoming: a call rang, but this browser is not a calling station — ignored");
      return;
    }
    const { list, added } = addIncoming(await readIncoming(), call, tabId, Date.now());
    await chrome.storage.session.set({ [INCOMING_CALLS_KEY]: list });
    if (added) {
      msgLog(
        `incoming: a ${call.isVideo ? "video" : "voice"} call is ringing (${call.waCallId.startsWith("dom-") ? "seen on the page" : "WhatsApp's call store"}` +
          `${call.phone ? "" : ", number unknown"}${call.isGroup ? ", group call" : ""})`,
      );
    }
  });
}

function noteIncomingEnded(waCallId: unknown): Promise<void> {
  return serializedIncoming(async () => {
    if (typeof waCallId !== "string") return;
    const list = await readIncoming();
    const next = endIncoming(list, waCallId);
    if (next.length === list.length) return;
    await chrome.storage.session.set({ [INCOMING_CALLS_KEY]: next });
    msgLog("incoming: a ring stopped");
  });
}

async function takeIncomingCalls(): Promise<StationIncomingCall[]> {
  // Station mode: wa-hook watches for calls only once this is on.
  if (!(await messagingEnabled())) await enableMessaging();
  return serializedIncoming(async () => {
    const { taken, list } = takeIncoming(await readIncoming(), Date.now());
    await chrome.storage.session.set({ [INCOMING_CALLS_KEY]: list });
    return taken;
  });
}

async function answerIncomingCall(request: StationCallRequest & { waCallId: string }): Promise<BridgeResult> {
  const waCallId = typeof request?.waCallId === "string" ? request.waCallId : "";
  if (!waCallId) return { ok: false, error: "No incoming call to answer" };
  const busy = await stationCallBusy();
  if (busy) return { ok: false, error: `Not answering: ${busy}` };
  const refused = await settlePreviousCall();
  if (refused) return refused;
  const ring = (await readIncoming()).find((entry) => entry.call.waCallId === waCallId) ?? null;
  const tabId = ring?.tabId ?? (await chrome.tabs.query({ url: WHATSAPP_TABS }))[0]?.id;
  if (tabId === undefined) return { ok: false, error: "No WhatsApp Web tab is open" };

  const now = Date.now();
  const call: ActiveCall = {
    callId: request.callId,
    recorderToken: request.recorderToken,
    apiBase: request.apiBase,
    phone: request.phone,
    requestedAt: now,
    tabId,
    // Set now: no reload of the tab may ever dial this call out (callForTab).
    dialedAt: now,
    lead: request.lead,
    agent: requestAgent(request),
    station: true,
    inbound: true,
  };
  await rememberCall(call);
  startTiming(call.callId, request.clickedAt);
  trace(call.callId, "Extension: answering an incoming call");
  await setActiveCall(call);
  const answer = await askAgent<BridgeResult>(tabId, { target: "wa-agent", type: "answer", call: waCall(call) }, ANSWER_TIMEOUT_MS);
  if (answer.kind === "answer" && answer.result?.ok) return { ok: true };
  const error =
    answer.kind === "answer"
      ? answer.result && !answer.result.ok
        ? answer.result.error
        : "WhatsApp Web gave an unexpected answer"
      : answer.kind === "timeout"
        ? "WhatsApp Web did not take the call in time"
        : "WhatsApp Web's tab did not answer (still loading, or opened before this extension build)";
  trace(call.callId, `Extension: could not answer — ${error}`);
  await clearActiveCall(call.callId);
  return { ok: false, error };
}
