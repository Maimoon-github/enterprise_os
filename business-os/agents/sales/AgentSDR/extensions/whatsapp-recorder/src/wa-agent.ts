/**
 * The extension's hands on web.whatsapp.com (isolated world). For a call
 * placed from AgentSDR it opens the chat, arms wa-hook, clicks WhatsApp's
 * Voice call button, and ships the recording wa-hook produces to the service
 * worker, which uploads it.
 *
 * A chat reaches this tab one of two ways:
 *   - in place (fast): the service worker asks this already-loaded tab to open
 *     it. A wa.me link clicked inside the page is handled by WhatsApp itself —
 *     the chat opens in about a second, or its "isn't on WhatsApp" popup
 *     shows — with no reload. The chat header is checked before anything is
 *     dialed; if the right chat can't be confirmed, the service worker falls
 *     back to reloading the tab.
 *   - by reload: the tab was (re)loaded at web.whatsapp.com/send?phone=…, and
 *     the service worker's answer to this script's hello says which call.
 *
 * The call's progress — dialing, ringing, recording, upload, transcript — is
 * shown in AgentSDR, not here: each phase goes to the service worker, which
 * relays it to the AgentSDR tab that placed the call (its live call strip).
 *
 * A rep call on a calling station (`repRelay`): the rep talks from their own
 * AgentSDR tab, and this script carries the audio through AgentSDR's relay
 * (rep-relay.ts) — the rep's voice down to wa-hook as agent-play, the lead's
 * side (wa-hook's relay-audio, from dialing on) up. It dials at once; the
 * rep's hang-up arriving on the relay presses End call.
 */

import { REP_RELAY_SAMPLE_RATE, type RecorderCallPhase, type RecorderCallStatus } from "../../../src/lib/calls/contract";
import { digitsOnly } from "../../../src/lib/calls/digits";
import { whatsappContactName, type WhatsappContactName } from "../../../src/lib/calls/whatsappContact";
import { LiveAgent } from "./live-agent";
import { RepRelay } from "./rep-relay";
import { pcm16Wav } from "./wav";
import type { StationInboundMessage } from "../../../src/lib/calls/stationContract";
import { isNonPersonalJid, jidToPhone, parseMessageId, parsePrePlainText } from "./inbound";
import {
  AGENT_MESSAGING_SOURCE,
  AGENT_SOURCE,
  HOOK_MESSAGING_SOURCE,
  HOOK_SOURCE,
  type AgentToHook,
  type AgentToHookMessaging,
  type HookToAgent,
  type HookToAgentMessaging,
} from "./wa-protocol";
import {
  WA_HEARD_AUDIO_PORT,
  WA_RECORDING_PORT,
  type AgentCommand,
  type AgentTokenResult,
  type BackgroundMessage,
  type BridgeResult,
  type ProbeResult,
  type WaCall,
  type WaHeardAudioPortMessage,
  type WaRecordingPortMessage,
  type WaScanResult,
  type WaSendOutcome,
} from "./messages";

/** WhatsApp Web can take a while to load a chat after a cold start. */
const DIAL_TIMEOUT_MS = 45_000;
/** How long an in-place open gets to show the right chat before the reload fallback. */
const OPEN_TIMEOUT_MS = 6_000;
const POLL_MS = 500;
/**
 * How long an open chat may go without a Voice call button before it is
 * taken as one WhatsApp can't call — a business number run through Meta's
 * API (seen 5 Oct 2026: a brand's number on a lead's profile).
 */
const NO_CALL_BUTTON_MS = 8_000;
/** The New contact form gets this long; past it the call goes ahead unsaved. */
const CONTACT_SAVE_TIMEOUT_MS = 8_000;
const OPEN_POLL_MS = 150;
/** Base64 chunks per port message; a runtime message tops out at 64 MB. */
const CHUNK_BYTES = 3 * 1024 * 1024;
const TRANSCRIPT_POLL_MS = 4_000;
/**
 * The pause after a call ends before the rep is taken back to AgentSDR to
 * mark the outcome; longer when WhatsApp's own popup explains why.
 */
const RETURN_DELAY_MS = 1_500;
const RETURN_DELAY_WITH_POPUP_MS = 2_500;
/** Transcription usually takes well under a minute; stop watching after this. */
const TRANSCRIPT_WATCH_MS = 3 * 60 * 1000;

let call: WaCall | null = null;
/** The AI voice agent's session on the current call, when it is an agent call. */
let agent: LiveAgent | null = null;
let agentCallId: string | null = null;
/** A rep call's audio through AgentSDR's relay, while it is on. */
let relay: RepRelay | null = null;
/** A call that ended before Voice call was pressed (wa-hook reported it not answered — the rep hung up early, say): never dial it. */
let endedBeforeDial: string | null = null;
/** Calls whose recording is on its way to the service worker. */
const shipping = new Set<string>();
/**
 * The chat header last confirmed for each number. Calling the same number
 * again leaves its chat open and the header unchanged, which would otherwise
 * wait out the whole confirmation window (5.9 s, measured 29 Sep 2026).
 */
const confirmedTitles = new Map<string, string>();

/** Records a timed step for the timing table (the service worker stamps the time). */
function trace(callId: string, step: string): void {
  void send({ target: "background", type: "wa:trace", callId, step }).catch(() => {});
  if (call?.station || call?.agent) pageLog(`${new Date().toISOString().slice(11, 23)} ${step}`);
}

/**
 * On a cloud station, every step is also written into a hidden element in
 * the page, which the call worker reads (page.evaluate) and empties.
 * CloakBrowser hides console messages, and the service worker's own log is
 * lost whenever Chrome restarts it; the page lives as long as the call.
 */
const PAGE_LOG_ID = "agentsdr-station-log";
function pageLog(line: string): void {
  let element = document.getElementById(PAGE_LOG_ID);
  if (!element) {
    element = document.createElement("template");
    element.id = PAGE_LOG_ID;
    document.documentElement.append(element);
  }
  element.setAttribute("data-lines", `${element.getAttribute("data-lines") ?? ""}${line}\n`);
}

/** Sends a phase of the current call on to the AgentSDR tab that placed it. */
function phase(next: RecorderCallPhase): void {
  if (call) void send({ target: "background", type: "wa:phase", callId: call.callId, phase: next }).catch(() => {});
}

/**
 * Presses WhatsApp's End call through wa-hook, which can reach the
 * picture-in-picture window WhatsApp moves the call into when this tab is in
 * the background. Resolves to whether a button was found and pressed.
 */
function endCall(callId: string): Promise<boolean> {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => finish(false), 1_500);
    function finish(clicked: boolean) {
      clearTimeout(timeout);
      window.removeEventListener("message", onResult);
      resolve(clicked);
    }
    function onResult(event: MessageEvent) {
      const data = event.data as HookToAgent | null;
      if (event.source === window && data?.source === HOOK_SOURCE && data.type === "end-result" && data.callId === callId) {
        finish(data.clicked);
      }
    }
    window.addEventListener("message", onResult);
    toHook({ source: AGENT_SOURCE, type: "end-call", callId });
  });
}
window.addEventListener("message", onHookMessage);

// Loaded by the reload path: the service worker says which call, if any.
void send<WaCall | null>({ target: "background", type: "wa:hello" })
  .then((pending) => {
    if (pending) void placeCall(pending);
  })
  .catch(() => {});

// Already loaded: open a chat in place, then place the call if there is one.
chrome.runtime.onMessage.addListener((message: AgentCommand, _sender, sendResponse) => {
  if (message.target !== "wa-agent") return;
  if (message.type === "probe") {
    void probe().then(sendResponse);
    return true;
  }
  if (message.type === "end") {
    void endCall(message.callId).then((clicked) =>
      sendResponse(
        (clicked ? { ok: true } : { ok: false, error: "WhatsApp's End call button isn't showing" }) satisfies BridgeResult,
      ),
    );
    return true;
  }
  if (message.type === "answer") {
    sendResponse(answerCall(message.call));
    return;
  }
  if (message.type !== "open") return; // station messaging: its own listener, below
  if (message.call) trace(message.call.callId, "WhatsApp tab: asked to open the chat in place");
  const savedName = whatsappContactName(message.call?.lead ?? null)?.display ?? null;
  void openInPlace(message.phone, message.text, message.call?.callId ?? null, savedName).then((outcome) => {
    if (outcome === "failed") {
      sendResponse({ ok: false, error: "Couldn't confirm the chat opened in place" } satisfies BridgeResult);
      return;
    }
    sendResponse({ ok: true } satisfies BridgeResult);
    if (!message.call) return;
    if (outcome === "not-on-whatsapp") reportNotOnWhatsApp(message.call);
    else void placeCall(message.call);
  });
  return true; // answers asynchronously
});

async function placeCall(next: WaCall): Promise<void> {
  call = next;
  const repCall = next.station && next.repRelay !== null && !next.agent;
  trace(
    next.callId,
    `WhatsApp tab: placing the call (${repCall ? "rep call (relay)" : `agent ${next.agent}`}, station ${next.station}, speakers ${!next.station})`,
  );
  toHook({ source: AGENT_SOURCE, type: "arm", callId: next.callId, agent: next.agent, monitor: !next.station, ...(repCall ? { repRelay: true } : {}) });
  // Opened now, so the rep hears the call from its first ring.
  if (repCall) startRelay(next);
  else stopRelay();
  // The AI's session opens now, not when WhatsApp's call session starts: that
  // came 4 s after Voice call on the call worker, and a lead who picked up at
  // once found the AI not ready, so its greeting could not be prepared while
  // WhatsApp connected (27 Oct 2026).
  if (next.agent) startAgent(next.callId);
  phase({ kind: "opening" });
  trace(next.callId, "WhatsApp tab: looking for the Voice call button");

  const savedName = whatsappContactName(next.lead)?.display ?? null;
  const outcome = await dial(next, savedName, () => saveContactIfNew(next));
  if (outcome === "dialed") {
    trace(next.callId, "WhatsApp tab: pressed Voice call");
    void send({ target: "background", type: "wa:dialed", callId: next.callId, pressed: true });
    phase({ kind: "calling" });
  } else if (outcome === "not-on-whatsapp") {
    stopCallAudio();
    reportNotOnWhatsApp(next);
  } else if (outcome === "no-call-button") {
    stopCallAudio();
    reportNotOnWhatsApp(next, true);
  } else if (outcome === "ended") {
    trace(next.callId, "WhatsApp tab: the call ended before Voice call was pressed — not dialing");
  } else {
    // Counted as dialed so a later reload of this tab never dials on its own;
    // still armed, so if the rep places the call by hand it is recorded anyway.
    void send({ target: "background", type: "wa:dialed", callId: next.callId, pressed: false });
    phase({ kind: "manual-dial" });
  }
}

/**
 * Answers the incoming call ringing in this tab as `next` (station mode only;
 * the service worker sends this only for a call AgentSDR chose to answer).
 * Armed first — wa-hook gives WhatsApp the agent's voice, and records, only
 * on an armed call — and the agent's session opens while it still rings; then
 * wa-hook presses Accept. From the pick-up on it is a placed call's path.
 */
function answerCall(next: WaCall): BridgeResult {
  call = next;
  trace(next.callId, `WhatsApp tab: answering an incoming call (agent ${next.agent})`);
  stopRelay();
  toHook({ source: AGENT_SOURCE, type: "arm", callId: next.callId, agent: next.agent, monitor: false });
  if (next.agent) startAgent(next.callId);
  phase({ kind: "ringing" });
  toHook({ source: AGENT_SOURCE, type: "accept-call", callId: next.callId });
  return { ok: true };
}

/** `noCallButton`: the chat opened, but WhatsApp offers no way to call it. */
function reportNotOnWhatsApp(target: WaCall, noCallButton = false): void {
  toHook({ source: AGENT_SOURCE, type: "disarm" });
  void send({ target: "background", type: "wa:not-on-whatsapp", callId: target.callId, noCallButton });
  call = target;
  phase({ kind: "not-on-whatsapp", noCallButton });
  returnToApp(target.callId, RETURN_DELAY_WITH_POPUP_MS);
}

/** Once a call is over, back to the AgentSDR tab it was placed from. */
function returnToApp(callId: string, delayMs: number): void {
  setTimeout(() => void send({ target: "background", type: "wa:focus-app", callId, auto: true }), delayMs);
}

/**
 * Which calls this tab is still busy with: one wa-hook is recording or
 * finishing off, and any whose recording is being uploaded. The service
 * worker asks before it gives up on a call as lost.
 */
function probe(): Promise<ProbeResult> {
  return new Promise((resolve) => {
    const busy = () => [...shipping];
    const timeout = setTimeout(() => finish(null), 1_000);
    function finish(hookCallId: string | null) {
      clearTimeout(timeout);
      window.removeEventListener("message", onResult);
      resolve({ busyCallIds: hookCallId ? [...busy(), hookCallId] : busy() });
    }
    function onResult(event: MessageEvent) {
      const data = event.data as HookToAgent | null;
      if (event.source === window && data?.source === HOOK_SOURCE && data.type === "probe-result") finish(data.callId);
    }
    window.addEventListener("message", onResult);
    toHook({ source: AGENT_SOURCE, type: "probe" });
  });
}

/**
 * Waits for the chat's Voice call button, runs `beforePress` once, then
 * presses it — only while the lead's chat is the one open. The first chat
 * header seen is the lead's (just confirmed in place, or opened by the
 * reload's URL); if another chat replaces it, nothing is pressed. A chat
 * that stays open without a Voice call button is "no-call-button".
 */
async function dial(
  target: WaCall,
  savedName: string | null,
  beforePress: () => Promise<void>,
): Promise<"dialed" | "not-on-whatsapp" | "no-call-button" | "ended" | "timeout"> {
  const deadline = Date.now() + DIAL_TIMEOUT_MS;
  const digits = digitsOnly(target.phone);
  let leadTitle: string | null = null;
  let chatSeenAt = 0;
  let prepared = false;
  while (Date.now() < deadline) {
    if (endedBeforeDial === target.callId) return "ended";
    if (invalidNumberShown()) return "not-on-whatsapp";
    const title = chatTitle();
    if (title && !leadTitle) {
      leadTitle = title;
      chatSeenAt = Date.now();
    }
    // Saving the lead as a contact renames its header to the saved name.
    if (title && leadTitle && title !== leadTitle && title !== savedName && digitsOnly(title) !== digits) {
      trace(target.callId, `WhatsApp tab: another chat opened ("${title}", expected "${leadTitle}") — not dialing`);
      return "timeout";
    }
    const button = title ? voiceCallButton() : null;
    if (title && !button && chatSeenAt && Date.now() - chatSeenAt > NO_CALL_BUTTON_MS) {
      trace(target.callId, `WhatsApp tab: chat "${title}" has no Voice call button`);
      return "no-call-button";
    }
    if (button && !button.disabled) {
      if (!prepared) {
        prepared = true;
        await beforePress();
        chatSeenAt = Date.now();
        continue; // the form may have re-rendered the chat; find the button afresh
      }
      pressLikeUser(button);
      return "dialed";
    }
    await sleep(POLL_MS);
  }
  return "timeout";
}

// --- saving a new lead as a WhatsApp contact -----------------------------------

/**
 * The first time a lead is called, their chat header reads their bare
 * number. Saving them as "First (Company)" means a callback or a reply shows
 * who it is, and the next call finds them by that name in the chat list.
 * WhatsApp-only: "Sync contact to phone" is left off. Never holds up the call
 * for long — any failure is noted and the call goes ahead.
 */
async function saveContactIfNew(next: WaCall): Promise<void> {
  const name = whatsappContactName(next.lead);
  const digits = digitsOnly(next.phone);
  const title = chatTitle();
  if (!name || !title || digitsOnly(title) !== digits) return; // already a contact, or unknown
  trace(next.callId, `WhatsApp tab: saving the lead as "${name.display}"`);
  try {
    await Promise.race([
      saveContact(name, digits),
      sleep(CONTACT_SAVE_TIMEOUT_MS).then(() => {
        throw new Error(`the New contact form took over ${CONTACT_SAVE_TIMEOUT_MS / 1000}s`);
      }),
    ]);
    confirmedTitles.set(digits, name.display);
    trace(next.callId, "WhatsApp tab: contact saved");
  } catch (error) {
    trace(next.callId, `WhatsApp tab: contact not saved (${error instanceof Error ? error.message : String(error)})`);
  } finally {
    await closeContactForm();
  }
}

async function saveContact(name: WhatsappContactName, digits: string): Promise<void> {
  press(await waitFor(() => document.querySelector<HTMLElement>('button[aria-label="New chat"]'), "the New chat button"));
  press(await waitFor(() => elementWithText("New contact"), "the New contact option"));
  const first = await waitFor(() => textbox("First name"), "the First name field");
  typeInto(first, name.firstName);
  if (name.lastName) typeInto(await waitFor(() => textbox("Last name"), "the Last name field"), name.lastName);

  // The form's country picker defaults to the rep's country ("IN +91"); only
  // a number from that country can be entered without changing it.
  const code = await waitFor(formCountryCode, "the form's country code");
  if (!digits.startsWith(code)) throw new Error(`the number is not a +${code} number, the form's default country`);
  const phone = await waitFor(
    () => document.querySelector<HTMLInputElement>('input[aria-label="Phone number"]'),
    "the Phone number field",
  );
  const national = digits.slice(code.length);
  typeInto(phone, national);
  // A controlled field can ignore typed text; set it the way React notices.
  if (digitsOnly(phone.value) !== national) setInputValue(phone, national);

  const save = await waitFor(saveButton, "an enabled Save button").catch((error: unknown) => {
    const form = commonAncestor(first, phone);
    throw new Error(
      `${error instanceof Error ? error.message : String(error)}; phone field "${phone.value}"; form buttons: ${describeButtons(form)}`,
    );
  });
  press(save);
  // Saved once the form is gone.
  await waitFor(() => (textbox("First name") ? null : document.body), "the form to close");
}

/**
 * The country code in the form's picker ("IN +91" → "91"). By visible text:
 * the picker's full textContent also carries its dropdown icon's label.
 */
function formCountryCode(): string | null {
  for (const element of Array.from(document.querySelectorAll<HTMLElement>('[role="button"]'))) {
    const match = /(?:^|\s)[A-Z]{2}\s*\+(\d{1,4})(?:\s|$)/.exec(element.innerText?.trim() ?? "");
    if (match) return match[1];
  }
  return null;
}

/**
 * Leaves the New contact / New chat panels, back to the chat list — before
 * the call is placed. Backing out of a half-filled form may ask to discard
 * it; that prompt is answered too, or it would sit over the call.
 */
async function closeContactForm(): Promise<void> {
  for (let i = 0; i < 4; i++) {
    const discard = elementWithText("Discard") ?? elementWithText("Discard changes");
    if (discard) {
      press(discard);
      await sleep(250);
      continue;
    }
    if (!textbox("First name") && !elementWithText("New contact")) return;
    document.querySelector<HTMLElement>('#side button[aria-label="Back"], button[aria-label="Back"]')?.click();
    await sleep(250);
  }
}

/** The form's confirm control: labelled Save/Done/Create/Add/Confirm, or a tick icon. */
function saveButton(): HTMLElement | null {
  const labelled = Array.from(document.querySelectorAll<HTMLElement>("button[aria-label], [role='button'][aria-label]")).find(
    (element) => /^(save|done|create|add contact|confirm)/i.test(element.getAttribute("aria-label") ?? ""),
  );
  const ticked = Array.from(document.querySelectorAll<HTMLElement>("[data-icon]"))
    .find((icon) => /^(checkmark|check|done)/i.test(icon.getAttribute("data-icon") ?? ""))
    ?.closest<HTMLElement>("button, [role='button']");
  const button = labelled ?? ticked ?? elementWithText("Save");
  const control = button?.closest<HTMLElement>("button, [role='button']") ?? button;
  if (!control || control.hasAttribute("disabled") || control.getAttribute("aria-disabled") === "true") return null;
  return button;
}

function textbox(label: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[role="textbox"][aria-label="${label}"]`);
}

/**
 * The element holding exactly this visible text — the innermost one, so a
 * press on it bubbles through every handler above it, as a real click
 * would. Matching a whole row's text failed for "New contact": the row
 * carries its icon's label too (29 Sep 2026).
 */
function elementWithText(text: string): HTMLElement | null {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.textContent?.trim() === text && node.parentElement?.offsetParent !== null) return node.parentElement;
  }
  return null;
}

/** Sets a React-controlled input: the native setter, then the input event React listens for. */
function setInputValue(input: HTMLInputElement, value: string): void {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function commonAncestor(a: HTMLElement, b: HTMLElement): HTMLElement {
  let node: HTMLElement | null = a;
  while (node && !node.contains(b)) node = node.parentElement;
  return node ?? document.body;
}

/** For diagnosis: every control near the form, by label, icon or text. */
function describeButtons(scope: HTMLElement): string {
  const root = scope.parentElement?.parentElement ?? scope;
  const controls = Array.from(root.querySelectorAll<HTMLElement>("button, [role='button'], [data-icon]"));
  const described = controls
    .map((element) =>
      [
        element.getAttribute("aria-label"),
        element.getAttribute("data-icon") && `icon:${element.getAttribute("data-icon")}`,
        element.innerText?.trim().slice(0, 20),
        element.hasAttribute("disabled") || element.getAttribute("aria-disabled") === "true" ? "(disabled)" : null,
      ]
        .filter(Boolean)
        .join(" "),
    )
    .filter(Boolean);
  return [...new Set(described)].slice(0, 25).join(" | ") || "none";
}

/** Types as a user would — insertText fires the input events WhatsApp's fields listen to. */
function typeInto(element: HTMLElement, text: string): void {
  element.focus();
  if (element instanceof HTMLInputElement) element.select();
  document.execCommand("insertText", false, text);
}

/**
 * Presses a button with the whole sequence a real mouse click produces —
 * hover, press, focus, release, click — rather than a bare click(). Placing a
 * call this way seemed to set it up more slowly than the rep's own click,
 * which WhatsApp may partly prepare on hover or press. It is the same set
 * of events WhatsApp already handles for a real click.
 */
function pressLikeUser(element: HTMLElement): void {
  const rect = element.getBoundingClientRect();
  const at = {
    bubbles: true,
    cancelable: true,
    composed: true,
    view: window,
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
    button: 0,
  };
  const pointer = { ...at, pointerId: 1, pointerType: "mouse", isPrimary: true };
  element.dispatchEvent(new PointerEvent("pointerover", pointer));
  element.dispatchEvent(new MouseEvent("mouseover", at));
  element.dispatchEvent(new PointerEvent("pointerdown", { ...pointer, buttons: 1 }));
  element.dispatchEvent(new MouseEvent("mousedown", { ...at, buttons: 1 }));
  element.focus();
  element.dispatchEvent(new PointerEvent("pointerup", pointer));
  element.dispatchEvent(new MouseEvent("mouseup", at));
  element.dispatchEvent(new MouseEvent("click", { ...at, detail: 1 }));
}

/** A full press: WhatsApp's list items react to mousedown, buttons to click. */
function press(element: HTMLElement): void {
  for (const type of ["mousedown", "mouseup", "click"] as const) {
    element.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
  }
}

async function waitFor<T>(find: () => T | null, what: string, timeoutMs = 3_000): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const found = find();
    if (found) return found;
    await sleep(100);
  }
  throw new Error(`${what} did not appear`);
}

// --- opening a chat in place -------------------------------------------------

/**
 * Opens the chat for `phone` without reloading, and confirms it is the one
 * showing: its header reads the number (a lead not in the rep's contacts), or
 * the header changed from the chat that was open before (a saved contact).
 * Anything short of that is "failed" and the caller reloads instead — the
 * next step may dial, so a guess is never good enough.
 */
async function openInPlace(
  phone: string,
  text: string | null,
  callId: string | null,
  /** The name the extension saves this lead under, once it has — "Rahul (Acme)". */
  savedName: string | null = null,
  /** Where the steps go when there is no call (station messaging). */
  log?: (step: string) => void,
): Promise<"opened" | "not-on-whatsapp" | "failed"> {
  const note = (step: string) => {
    if (callId) trace(callId, step);
    else log?.(step);
  };
  const digits = digitsOnly(phone);
  const before = chatTitle();

  // Fastest first: the chat is already open, or it is in the chat list —
  // both skip the server check WhatsApp runs for a wa.me link (about 5 s,
  // measured 29 Sep 2026). A lead not saved as a contact shows as its number
  // in both places, so the digits confirm it is the right chat.
  if (before && (digitsOnly(before) === digits || before === savedName)) {
    note("WhatsApp tab: the chat is already open");
    if (text) await typeIntoComposer(text);
    return "opened";
  }
  if (await openFromChatList(digits, savedName)) {
    note("WhatsApp tab: opened the chat from the chat list");
    if (text) await typeIntoComposer(text);
    return "opened";
  }

  if (!clickChatLink(digits, text)) {
    note("WhatsApp tab: WhatsApp ignored the chat link — falling back to a reload");
    return "failed";
  }
  note("WhatsApp tab: chat link handled by WhatsApp");

  const deadline = Date.now() + OPEN_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(OPEN_POLL_MS);
    if (invalidNumberShown()) return "not-on-whatsapp";
    const title = chatTitle();
    if (!title) continue;
    const sameChatAsLastTime = title === before && confirmedTitles.get(digits) === title;
    if (
      digitsOnly(title) === digits ||
      title === savedName ||
      (before !== null && title !== before) ||
      before === null ||
      sameChatAsLastTime
    ) {
      confirmedTitles.set(digits, title);
      note(`WhatsApp tab: chat confirmed ("${title}")${sameChatAsLastTime ? " — already open from the last call" : ""}`);
      if (text) await typeIntoComposer(text);
      return "opened";
    }
  }
  note(`WhatsApp tab: chat not confirmed in ${OPEN_TIMEOUT_MS / 1000}s (header "${chatTitle() ?? "none"}", was "${before ?? "none"}") — falling back to a reload`);
  return "failed";
}

/**
 * Opens a chat by its row in the chat list, when the row is titled with the
 * number (a lead not saved as a contact), and confirms it by the header.
 * WhatsApp's rows react to mousedown, so the full press is dispatched.
 */
async function openFromChatList(digits: string, savedName: string | null): Promise<boolean> {
  const titles = Array.from(document.querySelectorAll<HTMLElement>("#pane-side span[title]"));
  const matches = (value: string | null | undefined) =>
    Boolean(value) && (digitsOnly(value ?? "") === digits || value === savedName);
  const title = titles.find((span) => matches(span.getAttribute("title")));
  const row = title?.closest<HTMLElement>('[role="gridcell"], [role="listitem"], [role="row"]') ?? title;
  if (!row) return false;
  for (const type of ["mousedown", "mouseup", "click"] as const) {
    row.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
  }
  const deadline = Date.now() + 2_000;
  while (Date.now() < deadline) {
    await sleep(OPEN_POLL_MS);
    if (matches(chatTitle())) return true;
  }
  return false;
}

/**
 * Clicks a wa.me link inside the page. WhatsApp handles it itself and
 * cancels the navigation; if it ever stops doing that, the navigation is
 * cancelled here instead (never leave WhatsApp) and this returns false.
 */
function clickChatLink(digits: string, text: string | null): boolean {
  const anchor = document.createElement("a");
  anchor.href = `https://wa.me/${digits}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
  let handled = false;
  // On window, bubbling: runs after WhatsApp's own document-level handler.
  const guard = (event: Event) => {
    if (event.target !== anchor) return;
    handled = event.defaultPrevented;
    event.preventDefault();
  };
  window.addEventListener("click", guard);
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.removeEventListener("click", guard);
  return handled;
}

/** The open chat's name as its header shows it — the number, for a non-contact. */
function chatTitle(): string | null {
  const header = document.querySelector<HTMLElement>("#main header");
  const first = header?.innerText.split("\n").map((line) => line.trim()).find(Boolean);
  return first ?? null;
}

/** Puts the follow-up in the message box unless WhatsApp already did; never sends it. */
async function typeIntoComposer(text: string): Promise<void> {
  const deadline = Date.now() + 2_000;
  while (Date.now() < deadline) {
    const box = document.querySelector<HTMLElement>('#main footer [contenteditable="true"]');
    if (box) {
      if ((box.textContent ?? "").includes(text.slice(0, 24))) return;
      box.focus();
      document.execCommand("insertText", false, text);
      return;
    }
    await sleep(OPEN_POLL_MS);
  }
}

/**
 * The open chat's Voice call button — only one inside the conversation pane.
 * A business chat has none, and falling back to a Voice call button elsewhere
 * on the page once dialed the previous lead instead (5 Oct 2026).
 */
function voiceCallButton(): HTMLButtonElement | null {
  return document.querySelector<HTMLButtonElement>('#main button[aria-label="Voice call"]');
}

/**
 * WhatsApp's popup for a number it can't open: "Phone number shared via url
 * is invalid." after a reload, "The number … isn't on WhatsApp." in place.
 */
function invalidNumberShown(): boolean {
  const popups = document.querySelectorAll('[role="dialog"], [data-animate-modal-popup="true"]');
  return Array.from(popups).some((popup) => /invalid|isn.t on WhatsApp/i.test(popup.textContent ?? ""));
}

function onHookMessage(event: MessageEvent): void {
  if (event.source !== window) return;
  const data = event.data as HookToAgent | null;
  if (data?.source !== HOOK_SOURCE || !data.callId) return;
  if (!call || data.callId !== call.callId) return finishOtherCall(data);
  const callId = call.callId;

  switch (data.type) {
    case "dialing":
      phase({ kind: "ringing" });
      // Opened when the call was placed; a call dialed by hand starts it here.
      if (call.agent && agentCallId !== callId) startAgent(callId);
      break;
    case "agent-audio":
      agent?.sendAudio(data.pcm);
      break;
    case "relay-audio":
      relay?.sendLead(data.pcm);
      break;
    case "call-status":
      trace(callId, `WhatsApp shows "${data.text}"`);
      // They accepted; the audio link is still being set up.
      if (/^connecting/i.test(data.text.trim())) agent?.prepareGreeting();
      break;
    case "call-ui":
      trace(callId, "WhatsApp shows the call screen");
      void send({ target: "background", type: "wa:call-shown", callId });
      break;
    case "diag":
      trace(callId, `hook: ${data.text}`);
      break;
    case "accept-result":
      if (data.clicked) {
        trace(callId, `WhatsApp tab: pressed Accept (the call's buttons: ${data.labels || "none seen"})`);
        break;
      }
      // Nothing to press: the caller hung up, or WhatsApp's markup changed.
      trace(callId, `WhatsApp tab: no Accept button to press — not answered (buttons seen: ${data.labels || "none"})`);
      stopCallAudio();
      toHook({ source: AGENT_SOURCE, type: "disarm" });
      void send({ target: "background", type: "wa:not-answered", callId, dialedAt: Date.now(), endedAt: Date.now() });
      phase({ kind: "not-answered" });
      break;
    case "answered":
      agent?.greet();
      void send({ target: "background", type: "wa:answered", callId, answeredAt: data.answeredAt });
      phase({ kind: "on-call", answeredAt: data.answeredAt, timerSeen: data.timerSeen });
      break;
    case "audio-suspended":
      // AgentSDR's strip tells the rep to click anywhere in this tab; that
      // click is the user gesture Chrome needs to let the call audio play.
      phase({ kind: "audio-blocked" });
      document.addEventListener("click", () => toHook({ source: AGENT_SOURCE, type: "resume-audio" }), {
        once: true,
        capture: true,
      });
      break;
    case "not-answered":
      stopCallAudio();
      endedBeforeDial = callId;
      void send({ target: "background", type: "wa:not-answered", callId, dialedAt: data.dialedAt, endedAt: data.endedAt });
      phase({ kind: "not-answered" });
      returnToApp(callId, RETURN_DELAY_MS);
      break;
    case "recording":
      stopCallAudio();
      // The upload and transcription carry on in this tab while the rep is
      // back in AgentSDR, whose contact panel shows them arriving.
      void ship(callId, data.blob, data.startedAt, data.answeredAt, data.endedAt);
      returnToApp(callId, RETURN_DELAY_MS);
      break;
    case "recording-failed":
      stopCallAudio();
      void send({ target: "background", type: "wa:recording-failed", callId, error: data.error });
      phase({ kind: "error", message: `Recording failed: ${data.error}`, savedLocally: false });
      break;
  }
}

/** Streams the file to the service worker; keeps a local copy if that fails. */
/**
 * The end of a call this tab is no longer showing — an earlier call whose
 * session was closed when a new call was armed. Its outcome is still
 * reported and its recording still uploaded, but its phases are not sent to
 * AgentSDR's live strip, which now follows the new call.
 */
function finishOtherCall(data: HookToAgent): void {
  if (!data.callId) return;
  const callId = data.callId;
  if (data.type === "not-answered") {
    void send({ target: "background", type: "wa:not-answered", callId, dialedAt: data.dialedAt, endedAt: data.endedAt });
  } else if (data.type === "recording") {
    void ship(callId, data.blob, data.startedAt, data.answeredAt, data.endedAt, { reportPhases: false });
  } else if (data.type === "recording-failed") {
    void send({ target: "background", type: "wa:recording-failed", callId, error: data.error });
  }
}

async function ship(
  callId: string,
  blob: Blob,
  startedAt: number,
  answeredAt: number,
  endedAt: number,
  options: { reportPhases: boolean } = { reportPhases: true },
): Promise<void> {
  shipping.add(callId);
  try {
    await shipRecording(callId, blob, startedAt, answeredAt, endedAt, options.reportPhases ? phase : () => {});
  } finally {
    shipping.delete(callId);
  }
}

async function shipRecording(
  callId: string,
  blob: Blob,
  startedAt: number,
  answeredAt: number,
  endedAt: number,
  phase: (next: RecorderCallPhase) => void,
): Promise<void> {
  // Talk time: the recording also holds the ringing before the pick-up.
  const durationMs = endedAt - answeredAt;
  phase({ kind: "processing", durationMs, step: "uploading" });
  let result: BridgeResult;
  try {
    const port = chrome.runtime.connect({ name: WA_RECORDING_PORT });
    const answered = new Promise<BridgeResult>((resolve) => {
      port.onMessage.addListener((message: BridgeResult) => resolve(message));
      port.onDisconnect.addListener(() => resolve({ ok: false, error: "The extension closed the upload" }));
    });
    const postPart = (message: WaRecordingPortMessage) => port.postMessage(message);
    postPart({ type: "meta", callId, mimeType: blob.type, startedAt, answeredAt, endedAt });
    const bytes = new Uint8Array(await blob.arrayBuffer());
    for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
      postPart({ type: "chunk", data: toBase64(bytes.subarray(offset, offset + CHUNK_BYTES)) });
    }
    postPart({ type: "end" });
    result = await answered;
    port.disconnect();
  } catch (error) {
    result = { ok: false, error: error instanceof Error ? error.message : String(error) };
  }

  if (result.ok) {
    phase({ kind: "processing", durationMs, step: "transcribing" });
    if (call?.callId === callId) void watchTranscript(callId, durationMs);
  } else {
    saveLocally(blob, startedAt);
    phase({ kind: "error", message: `Upload failed: ${result.error}`, savedLocally: true });
  }
}

/** Follows the transcript on the server until it is ready, so AgentSDR's strip can show the summary. */
async function watchTranscript(callId: string, durationMs: number): Promise<void> {
  const deadline = Date.now() + TRANSCRIPT_WATCH_MS;
  while (Date.now() < deadline) {
    await sleep(TRANSCRIPT_POLL_MS);
    if (call?.callId !== callId) return; // a newer call took over the strip
    const status = await send<RecorderCallStatus | null>({ target: "background", type: "wa:status", callId }).catch(() => null);
    if (status?.transcriptStatus === "done") {
      phase({ kind: "done", durationMs, summary: status.summary, transcriptFailed: false });
      return;
    }
    if (status?.transcriptStatus === "failed") {
      phase({ kind: "done", durationMs, summary: null, transcriptFailed: true });
      return;
    }
  }
  // Still transcribing after the watch window: leave the strip saying so
  // rather than claim it finished. The summary lands in AgentSDR either way.
}

function saveLocally(blob: Blob, startedAt: number): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const extension = blob.type.startsWith("audio/ogg") ? "ogg" : "webm";
  anchor.href = url;
  anchor.download = `call-${new Date(startedAt).toISOString().replace(/[:.]/g, "-")}.${extension}`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

// --- the AI voice agent (trial) ------------------------------------------------

/** Opened while the call rings, so the agent is ready to speak the moment the lead picks up. */
function startAgent(callId: string): void {
  stopAgent();
  const session = new LiveAgent({
    play: (pcm, rate) => toHook({ source: AGENT_SOURCE, type: "agent-play", callId, pcm, rate }, [pcm]),
    interrupt: () => toHook({ source: AGENT_SOURCE, type: "agent-interrupt", callId }),
    hangup: () => toHook({ source: AGENT_SOURCE, type: "agent-hangup", callId }),
    trace: (step) => {
      console.info("[agentsdr agent]", step);
      trace(callId, step);
    },
    token: () => send<AgentTokenResult>({ target: "background", type: "wa:agent-token", callId }),
    outcome: (report) =>
      void send<BridgeResult>({ target: "background", type: "wa:agent-outcome", callId, outcome: report })
        .then((result) =>
          trace(callId, result.ok ? "AI agent: outcome saved" : `AI agent: could not save the outcome — ${result.error}`),
        )
        .catch((error: unknown) => trace(callId, `AI agent: could not save the outcome — ${String(error)}`)),
  });
  agent = session;
  agentCallId = callId;
  session.start().catch((error: unknown) => trace(callId, `AI agent: failed to start — ${String(error)}`));
}

function stopAgent(): void {
  const session = agent;
  const callId = agentCallId;
  agent = null;
  agentCallId = null;
  if (!session) return;
  const heard = session.takeHeardAudio();
  session.close();
  if (heard && callId) void sendHeardAudio(callId, heard);
}

/** The call is over (or never placed): the agent's session and a rep call's relay stop. */
function stopCallAudio(): void {
  stopAgent();
  stopRelay();
}

// --- a rep talking through this station ------------------------------------------

/**
 * Opens the rep call's relay: the rep's voice to wa-hook (WhatsApp's
 * microphone), the lead's side — sent by wa-hook as relay-audio — to the rep.
 * Its steps are traced, so they show in the worker's log and the timeline.
 */
function startRelay(next: WaCall): void {
  stopRelay();
  const access = next.repRelay;
  if (!access) return;
  const callId = next.callId;
  const session = new RepRelay({
    url: `${access.apiBase}/api/call-recorder/calls/${encodeURIComponent(callId)}/relay`,
    token: access.recorderToken,
    play: (pcm) => toHook({ source: AGENT_SOURCE, type: "agent-play", callId, pcm, rate: REP_RELAY_SAMPLE_RATE }, [pcm]),
    hangup: (why) => {
      trace(callId, `rep relay: ${why} — hanging up`);
      void endCall(callId);
    },
    trace: (step) => trace(callId, `rep relay: ${step}`),
  });
  relay = session;
  trace(callId, "rep relay: opening");
  session.start();
}

function stopRelay(): void {
  const session = relay;
  relay = null;
  session?.close();
}

/** The heard-audio test option: hands the WAV of what the agent heard to the service worker, which uploads it. */
async function sendHeardAudio(callId: string, pcm: Int16Array): Promise<void> {
  const wav = pcm16Wav(pcm, 16_000);
  const port = chrome.runtime.connect({ name: WA_HEARD_AUDIO_PORT });
  const post = (message: WaHeardAudioPortMessage) => port.postMessage(message);
  const result = new Promise<BridgeResult>((resolve) => {
    port.onMessage.addListener((message: BridgeResult) => resolve(message));
    port.onDisconnect.addListener(() => resolve({ ok: false, error: "the extension's worker went away" }));
  });
  post({ type: "meta", callId });
  for (let offset = 0; offset < wav.length; offset += CHUNK_BYTES) post({ type: "chunk", data: toBase64(wav.subarray(offset, offset + CHUNK_BYTES)) });
  post({ type: "end" });
  const answer = await result;
  trace(callId, answer.ok ? `AI agent: saved what it heard (${Math.round(pcm.length / 16_000)} s)` : `AI agent: could not save what it heard — ${answer.error}`);
  port.disconnect();
}

// =============================================================================
// --- station messaging (calling stations only) --------------------------------
// =============================================================================
//
// A calling station also sends and reads WhatsApp messages for AgentSDR (the
// call worker drives it through the service worker's agentsdrStation). Kept
// apart from the call path above, which it only reuses (openInPlace, probe,
// chatTitle, invalidNumberShown); it never runs during a call.
//
// Reading messages is wa-hook's job (WhatsApp's own message store), enabled
// only once the service worker's station mode asked for messages, so a rep's
// own WhatsApp Web is never read. When the store cannot be read, the service
// worker asks this script to scan the chat list's unread chats instead.

/** After a reload at /send?phone=…, how long WhatsApp gets to open the chat. */
const SEND_OPEN_AFTER_RELOAD_MS = 20_000;
/** How long a pressed Send gets to show the message in the chat. */
const SEND_CONFIRM_MS = 10_000;
/** Send pressed and nothing happened this long: try Enter in the message box. */
const SEND_ENTER_FALLBACK_MS = 1_500;
const FIND_SENT_WAIT_MS = 1_500;
/** After Send, the store is asked about the message from this long on (the page's row usually shows first). */
const SEND_STORE_CHECK_AFTER_MS = 1_000;
/** A DOM scan opens at most this many unread chats, and reads at most this many messages from each. */
const SCAN_MAX_CHATS = 10;
const SCAN_MAX_MESSAGES_PER_CHAT = 50;
const COMPOSER_SELECTOR = '#main footer [contenteditable="true"]';

let sendingMessage = false;

function msgLog(step: string): void {
  void send({ target: "background", type: "wa:msg-log", step }).catch(() => {});
}

window.addEventListener("message", onHookMessagingMessage);

// On every load, including a reload: read messages only on a station that asked for them.
void send<{ enabled: boolean } | undefined>({ target: "background", type: "wa:messaging-hello" })
  .then((answer) => {
    if (answer?.enabled) enableHookMessaging();
  })
  .catch(() => {});

chrome.runtime.onMessage.addListener((message: AgentCommand, _sender, sendResponse) => {
  if (message.target !== "wa-agent") return;
  if (message.type === "messaging-enable") {
    enableHookMessaging();
    sendResponse({ ok: true } satisfies BridgeResult);
    return;
  }
  if (message.type === "send-message") {
    void sendWhatsappMessage(message.phone, message.text, message.afterReload).then(sendResponse, (error: unknown) =>
      // Past this point Send may have been pressed: never say it is safe to retry.
      sendResponse({ ok: false, retryable: false, error: `Sending failed: ${describeError(error)}` } satisfies WaSendOutcome),
    );
    return true;
  }
  if (message.type === "scan-inbound") {
    void scanUnreadChats().then(sendResponse, (error: unknown) =>
      sendResponse({ ok: false, skipped: false, error: describeError(error) } satisfies WaScanResult),
    );
    return true;
  }
});

function enableHookMessaging(): void {
  toHookMessaging({ source: AGENT_MESSAGING_SOURCE, type: "messaging-enable" });
}

function onHookMessagingMessage(event: MessageEvent): void {
  if (event.source !== window) return;
  const data = event.data as HookToAgentMessaging | null;
  if (data?.source !== HOOK_MESSAGING_SOURCE) return;
  if (data.type === "messaging-source") {
    void send({ target: "background", type: "wa:messaging-source", capability: data.capability }).catch(() => {});
  } else if (data.type === "messages" && Array.isArray(data.messages) && data.messages.length) {
    void send({ target: "background", type: "wa:inbound", messages: data.messages }).catch(() => {});
  } else if (data.type === "messaging-log") {
    msgLog(`hook: ${data.text}`);
  } else if (data.type === "incoming-call" && data.call) {
    void send({ target: "background", type: "wa:incoming-call", call: data.call }).catch(() => {});
  } else if (data.type === "incoming-call-ended" && data.waCallId) {
    void send({ target: "background", type: "wa:incoming-ended", waCallId: data.waCallId }).catch(() => {});
  }
}

/** Why messaging must wait: a call is being placed, is on, or is being finished off here. Null when clear. */
async function callBlocksMessaging(): Promise<string | null> {
  if (agent) return "the AI agent is on a call";
  if (document.querySelector('[aria-label="End call"]')) return "WhatsApp shows a call";
  const probed = await probe();
  if (probed.busyCallIds.length) return `a call is in progress (${probed.busyCallIds[0].slice(0, 8)})`;
  return null;
}

/** Logged in and loaded: the chat list is showing. */
function whatsappReady(): boolean {
  return Boolean(document.querySelector("#pane-side"));
}

/**
 * Sends `text` to `phone` (digits) and confirms it showed in the chat. Never
 * reloads the tab itself: when the chat cannot be opened in place it answers
 * `reload` before anything is typed, and the service worker decides.
 */
async function sendWhatsappMessage(phone: string, text: string, afterReload: boolean): Promise<WaSendOutcome> {
  if (sendingMessage) return { ok: false, retryable: true, error: "Another message is being sent from this number" };
  sendingMessage = true;
  try {
    return await sendWhatsappMessageNow(digitsOnly(phone), text, afterReload);
  } finally {
    sendingMessage = false;
  }
}

async function sendWhatsappMessageNow(digits: string, text: string, afterReload: boolean): Promise<WaSendOutcome> {
  const busy = await callBlocksMessaging();
  if (busy) return { ok: false, retryable: true, error: `Not sent: ${busy}` };

  let opened: "opened" | "not-on-whatsapp" | "failed";
  if (afterReload) {
    msgLog(`send: WhatsApp reloaded at the chat with +${digits}; waiting for it`);
    opened = await waitForChatAfterReload(digits);
  } else {
    if (!whatsappReady()) return { ok: false, retryable: true, error: "WhatsApp Web is not ready (still loading, or not logged in)" };
    msgLog(`send: opening the chat with +${digits} in place`);
    opened = await openInPlace(digits, null, null, null, (step) => msgLog(`send: ${step}`));
  }
  if (opened === "not-on-whatsapp") {
    msgLog(`send: +${digits} is not on WhatsApp`);
    await dismissInvalidNumberPopup();
    return { ok: false, retryable: false, error: `+${digits} is not on WhatsApp` };
  }
  if (opened === "failed") {
    return afterReload
      ? { ok: false, retryable: true, error: "The chat did not open after reloading WhatsApp Web" }
      : { ok: false, reload: true, error: "The chat could not be opened in place" };
  }

  // Opening took a moment: a call may have started meanwhile. Nothing is typed yet.
  const busyNow = await callBlocksMessaging();
  if (busyNow) return { ok: false, retryable: true, error: `Not sent: ${busyNow}` };
  const box = await waitFor(() => document.querySelector<HTMLElement>(COMPOSER_SELECTOR), "the message box", 5_000).catch(() => null);
  if (!box) return { ok: false, retryable: true, error: "The chat has no message box (WhatsApp does not let this number message it)" };

  if (!(await typeMessage(box, text))) {
    await clearComposer(box);
    return { ok: false, retryable: true, error: "The message could not be typed into WhatsApp's message box" };
  }
  msgLog(`send: typed ${text.length} characters; pressing Send`);

  const before = outgoingRowIds();
  const pressedAt = Date.now();
  const button = sendButton();
  if (button) pressLikeUser(button);
  else {
    msgLog("send: no Send button found; pressing Enter");
    pressEnter(box);
  }

  // Confirmed by its row in the open chat, or — where WhatsApp Web's rows no
  // longer carry "true_…" data-ids (2.3000.105) — by WhatsApp's own store,
  // asked about once a second once the text has left the message box.
  let row: HTMLElement | null = null;
  let storeId: string | null = null;
  let nextStoreCheck = pressedAt + SEND_STORE_CHECK_AFTER_MS;
  let enterTried = !button;
  while (Date.now() - pressedAt < SEND_CONFIRM_MS) {
    await sleep(250);
    row = newOutgoingRow(before);
    if (row) break;
    if (!composerHasText() && Date.now() >= nextStoreCheck) {
      storeId = await findSentViaHook(digits, text, pressedAt - 5_000, null);
      if (storeId) break;
      nextStoreCheck = Date.now() + 1_000;
    }
    if (!enterTried && composerHasText() && Date.now() - pressedAt > SEND_ENTER_FALLBACK_MS) {
      enterTried = true;
      msgLog("send: Send did not take; pressing Enter");
      pressEnter(document.querySelector<HTMLElement>(COMPOSER_SELECTOR) ?? box);
    }
  }

  if (!row && storeId) {
    msgLog(`send: sent (${storeId}, from the store)`);
    return { ok: true, providerMessageId: storeId };
  }
  if (!row) {
    if (composerHasText()) {
      // Still in the box and nothing in the chat: it did not go.
      await clearComposer(document.querySelector<HTMLElement>(COMPOSER_SELECTOR) ?? box);
      msgLog("send: WhatsApp did not send it (the text stayed in the message box)");
      return { ok: false, retryable: true, error: "WhatsApp did not send the message (Send had no effect)" };
    }
    msgLog("send: the message box emptied but no sent message showed in the chat");
    return {
      ok: false,
      retryable: false,
      uncertain: true,
      error: `The message box emptied but the sent message did not show within ${SEND_CONFIRM_MS / 1000} s — it may have been sent`,
    };
  }

  const domId = row.getAttribute("data-id");
  const keyId = parseMessageId(domId)?.keyId ?? null;
  const storeFound = await findSentViaHook(digits, text, pressedAt - 5_000, keyId);
  const providerMessageId = storeFound ?? (parseMessageId(domId) ? domId : null);
  msgLog(`send: sent (${providerMessageId ?? "no id"}${storeFound ? ", from the store" : domId ? ", from the page" : ""})`);
  return { ok: true, providerMessageId };
}

/** After a load at /send?phone=…: the chat WhatsApp opens for it, or its "invalid number" popup. */
async function waitForChatAfterReload(digits: string): Promise<"opened" | "not-on-whatsapp" | "failed"> {
  const deadline = Date.now() + SEND_OPEN_AFTER_RELOAD_MS;
  while (Date.now() < deadline) {
    if (invalidNumberShown()) return "not-on-whatsapp";
    const title = chatTitle();
    // A fresh load opens no chat but the one in its URL.
    if (title && document.querySelector(COMPOSER_SELECTOR)) {
      msgLog(`send: chat open after the reload ("${title}"${digitsOnly(title) === digits ? "" : ", a saved contact"})`);
      return "opened";
    }
    await sleep(OPEN_POLL_MS);
  }
  msgLog(`send: no chat ${SEND_OPEN_AFTER_RELOAD_MS / 1000} s after the reload`);
  return "failed";
}

/** Answers WhatsApp's "isn't on WhatsApp" / "invalid" popup, so it does not sit over the next job. */
async function dismissInvalidNumberPopup(): Promise<void> {
  const popups = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"], [data-animate-modal-popup="true"]'));
  const popup = popups.find((element) => /invalid|isn.t on WhatsApp/i.test(element.textContent ?? ""));
  if (!popup) return;
  const ok = Array.from(popup.querySelectorAll<HTMLElement>('button, [role="button"]')).find((element) =>
    /^(ok|close)$/i.test(element.innerText?.trim() ?? ""),
  );
  if (ok) press(ok);
  else document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
  await sleep(300);
}

/** The message box's text, line breaks included — read from the nodes, so it needs no layout. */
function composerText(box: HTMLElement | null = document.querySelector<HTMLElement>(COMPOSER_SELECTOR)): string {
  if (!box) return "";
  let text = "";
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      text += node.textContent ?? "";
      return;
    }
    if (!(node instanceof HTMLElement)) return;
    if (node.tagName === "BR") {
      text += "\n";
      return;
    }
    if (node.tagName === "IMG") {
      text += node.getAttribute("alt") ?? "";
      return;
    }
    const block = node !== box && /^(P|DIV)$/.test(node.tagName);
    if (block && text && !text.endsWith("\n")) text += "\n";
    node.childNodes.forEach(walk);
  };
  walk(box);
  return text.replace(/[​﻿]/g, "");
}

function composerHasText(): boolean {
  return composerText().trim() !== "";
}

/** Same words in the same order, and no line break lost. Spacing is not compared. */
function composerMatches(actual: string, wanted: string): boolean {
  const squash = (value: string) => value.replace(/\s+/g, "");
  const lines = (value: string) => value.split("\n").filter((line) => line.trim()).length;
  return squash(actual) === squash(wanted) && lines(actual) >= lines(wanted);
}

async function clearComposer(box: HTMLElement): Promise<void> {
  box.focus();
  document.execCommand("selectAll");
  document.execCommand("delete");
  await sleep(100);
}

/**
 * Types the message without sending any of it. Tried first as one insertText
 * of the whole text; if WhatsApp's editor drops its line breaks, again line by
 * line with insertLineBreak between — what Shift+Enter inserts. Enter itself
 * sends, so it is never used to break a line.
 */
async function typeMessage(box: HTMLElement, raw: string): Promise<boolean> {
  const wanted = raw.replace(/\r\n?/g, "\n").trim();
  if (!wanted) return false;
  await clearComposer(box);
  if (composerHasText()) {
    msgLog("send: could not clear a draft in the message box");
    return false;
  }
  box.focus();
  document.execCommand("insertText", false, wanted);
  await sleep(200);
  if (composerMatches(composerText(), wanted)) return true;
  if (!wanted.includes("\n")) {
    msgLog(`send: the message box shows ${JSON.stringify(composerText().slice(0, 80))}, not the message`);
    return false;
  }
  msgLog("send: line breaks were lost; typing line by line");
  const current = document.querySelector<HTMLElement>(COMPOSER_SELECTOR) ?? box;
  await clearComposer(current);
  current.focus();
  wanted.split("\n").forEach((line, index) => {
    if (index > 0) document.execCommand("insertLineBreak");
    if (line) document.execCommand("insertText", false, line);
  });
  await sleep(200);
  if (composerMatches(composerText(), wanted)) return true;
  msgLog(`send: the message box shows ${JSON.stringify(composerText().slice(0, 80))}, not the message`);
  return false;
}

/** WhatsApp's Send: by its label, else by its icon. */
function sendButton(): HTMLElement | null {
  const labelled = document.querySelector<HTMLElement>(
    '#main footer button[aria-label="Send"], #main footer [role="button"][aria-label="Send"], #main button[aria-label="Send"]',
  );
  if (labelled) return labelled;
  const icon = document.querySelector<HTMLElement>(
    '#main footer [data-icon="send"], #main footer [data-icon="wds-ic-send-filled"], #main [data-icon="send"], #main [data-icon="wds-ic-send-filled"]',
  );
  return icon?.closest<HTMLElement>('button, [role="button"]') ?? icon ?? null;
}

function pressEnter(box: HTMLElement): void {
  box.focus();
  const init = { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true, composed: true };
  box.dispatchEvent(new KeyboardEvent("keydown", init));
  box.dispatchEvent(new KeyboardEvent("keypress", init));
  box.dispatchEvent(new KeyboardEvent("keyup", init));
}

/** The open chat's message rows sent from this number, by data-id ("true_<jid>_<key id>"). */
function outgoingRows(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('#main [data-id^="true_"]'));
}

function outgoingRowIds(): Set<string> {
  return new Set(outgoingRows().map((row) => row.getAttribute("data-id") ?? ""));
}

/** The chat's last sent row, when it was not there before Send. */
function newOutgoingRow(before: Set<string>): HTMLElement | null {
  const rows = outgoingRows();
  const last = rows[rows.length - 1];
  const id = last?.getAttribute("data-id");
  return last && id && !before.has(id) ? last : null;
}

/** Asks wa-hook for the sent message's id in WhatsApp's store; null when the store cannot say. */
async function findSentViaHook(chatDigits: string, body: string, sinceMs: number, keyId: string | null): Promise<string | null> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const found = await new Promise<string | null>((resolve) => {
      const requestId = crypto.randomUUID();
      const timeout = setTimeout(() => finish(null), FIND_SENT_WAIT_MS);
      function finish(id: string | null) {
        clearTimeout(timeout);
        window.removeEventListener("message", onResult);
        resolve(id);
      }
      function onResult(event: MessageEvent) {
        const data = event.data as HookToAgentMessaging | null;
        if (event.source === window && data?.source === HOOK_MESSAGING_SOURCE && data.type === "found-sent" && data.requestId === requestId) {
          finish(data.providerMessageId);
        }
      }
      window.addEventListener("message", onResult);
      toHookMessaging({ source: AGENT_MESSAGING_SOURCE, type: "find-sent", requestId, chatDigits, body: body.replace(/\r\n?/g, "\n").trim(), sinceMs, keyId });
    });
    if (found) return found;
    await sleep(500);
  }
  return null;
}

// --- reading unread chats from the page (when the store cannot be read) --------

/**
 * Opens each chat the chat list marks unread and reads its newest incoming
 * messages — as many as its unread count. Opening a chat marks it read,
 * which is the price of this fallback. Never while a call is on.
 */
async function scanUnreadChats(): Promise<WaScanResult> {
  const busy = await callBlocksMessaging();
  if (busy) return { ok: false, skipped: true, error: busy };
  if (sendingMessage) return { ok: false, skipped: true, error: "a message is being sent" };
  if (!whatsappReady()) return { ok: false, skipped: false, error: "WhatsApp Web is not ready (still loading, or not logged in)" };

  const unread = unreadChats();
  if (unread.length) msgLog(`scan: ${unread.length} unread chat(s) in the chat list`);
  const messages: StationInboundMessage[] = [];
  for (const chat of unread.slice(0, SCAN_MAX_CHATS)) {
    if (await callBlocksMessaging()) break;
    press(chat.row);
    const deadline = Date.now() + 3_000;
    while (Date.now() < deadline && chatTitle() !== chat.title) await sleep(OPEN_POLL_MS);
    if (chatTitle() !== chat.title) {
      msgLog(`scan: chat "${chat.title}" did not open`);
      continue;
    }
    await sleep(600); // its messages render a moment after the header
    messages.push(...readIncomingRows(chat.title, chat.count));
  }
  return { ok: true, messages };
}

/** Chat-list rows carrying an unread badge ("3 unread messages"), with their counts. */
function unreadChats(): { row: HTMLElement; title: string; count: number }[] {
  const counts = new Map<HTMLElement, number>();
  for (const badge of Array.from(document.querySelectorAll<HTMLElement>("#pane-side [aria-label]"))) {
    const label = badge.getAttribute("aria-label") ?? "";
    if (!/unread message/i.test(label)) continue;
    const row = badge.closest<HTMLElement>('[role="gridcell"], [role="listitem"], [role="row"]');
    if (!row) continue;
    const count = Number.parseInt(badge.textContent ?? "", 10) || Number.parseInt(label, 10) || 1;
    counts.set(row, Math.max(counts.get(row) ?? 0, count));
  }
  return Array.from(counts, ([row, count]) => ({ row, count, title: row.querySelector("span[title]")?.getAttribute("title") ?? "" })).filter(
    (chat) => chat.title,
  );
}

/** The open chat's newest `count` incoming messages. Groups (and anything not a person's chat) are skipped. */
function readIncomingRows(title: string, count: number): StationInboundMessage[] {
  const seen = new Set<string>();
  const rows = Array.from(document.querySelectorAll<HTMLElement>('#main [data-id^="false_"]')).filter((row) => {
    const id = row.getAttribute("data-id") ?? "";
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
  const parsed = rows.map((row) => ({ row, id: parseMessageId(row.getAttribute("data-id")) }));
  if (parsed.some(({ id }) => id && isNonPersonalJid(id.jid))) {
    msgLog(`scan: "${title}" is a group or broadcast — skipped`);
    return [];
  }
  const headerPhone = /^\+?[\d\s()-]{7,}$/.test(title) ? `+${digitsOnly(title)}` : null;
  const messages: StationInboundMessage[] = [];
  for (const { row, id } of parsed.slice(-Math.min(Math.max(count, 1), SCAN_MAX_MESSAGES_PER_CHAT))) {
    if (!id) continue;
    const meta = row.querySelector<HTMLElement>("[data-pre-plain-text]");
    const textElement = meta?.querySelector<HTMLElement>("span.selectable-text") ?? row.querySelector<HTMLElement>("span.selectable-text");
    const { sentAt } = parsePrePlainText(meta?.getAttribute("data-pre-plain-text"));
    messages.push({
      providerMessageId: row.getAttribute("data-id") ?? "",
      chatPhone: jidToPhone(id.jid) ?? headerPhone,
      chatJid: id.jid,
      chatName: headerPhone ? null : title,
      direction: "inbound",
      text: (textElement?.innerText ?? "").trim(),
      sentAt: sentAt ?? Date.now(),
      // A row with no text prefix is media, a voice note or the like.
      kind: meta ? null : "media",
    });
  }
  if (messages.length) msgLog(`scan: read ${messages.length} message(s) from "${title}"`);
  return messages;
}

function toHookMessaging(message: AgentToHookMessaging): void {
  window.postMessage(message, location.origin);
}

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// --- plumbing ------------------------------------------------------------------

function toHook(message: AgentToHook, transfer: Transferable[] = []): void {
  window.postMessage(message, location.origin, transfer);
}

function send<T = unknown>(message: BackgroundMessage): Promise<T> {
  return chrome.runtime.sendMessage<BackgroundMessage, T>(message);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
