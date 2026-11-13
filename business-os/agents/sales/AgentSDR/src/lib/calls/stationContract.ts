/**
 * Cloud calling: the shapes shared by the app, its API, and the call worker
 * (services/call-worker). Keep this file free of runtime imports — the
 * worker imports it across the repo, like the extension imports contract.ts.
 *
 * A calling station is one WhatsApp number whose WhatsApp Web runs in a
 * remote browser (a GoLogin profile, or Playwright's own Chromium for local
 * testing). The call worker opens that browser for each call and hands the
 * call to the recorder extension inside it (station mode); from there it is
 * the same AI-agent call a rep places from their laptop.
 */

import type { RecorderCallPhase, RecorderLead } from "./contract";

export const STATION_LAUNCHERS = ["cloak", "local", "gologin_sdk", "gologin_cloud"] as const;
/**
 * How the worker opens a station's browser:
 *   cloak          CloakBrowser (stealth Chromium) with a profile folder on the worker's disk; the
 *                  profile keeps its own fixed fingerprint and its WhatsApp login between calls;
 *   local          Playwright's Chromium with a profile folder on the worker's own disk (testing, self-hosted);
 *   gologin_sdk    the GoLogin SDK starts the profile on the worker's machine;
 *   gologin_cloud  GoLogin's Cloud Browser, reached over CDP.
 */
export type StationLauncher = (typeof STATION_LAUNCHERS)[number];

/** The launchers that open a GoLogin profile, and so need its id and the GoLogin integration. */
export function usesGoLogin(launcher: StationLauncher): boolean {
  return launcher === "gologin_sdk" || launcher === "gologin_cloud";
}

export const STATION_STATUSES = ["onboarding", "active", "paused", "logged_out", "banned"] as const;
export type StationStatus = (typeof STATION_STATUSES)[number];

/** A station as the app shows it. */
export type CallingStation = {
  id: string;
  name: string;
  /** E.164. */
  phone: string;
  launcher: StationLauncher;
  gologinProfileId: string | null;
  status: StationStatus;
  /** A call is running on it now. */
  busyCallId: string | null;
  /** Set while the worker is linking WhatsApp Web; see StationLinkState. */
  link: StationLinkState | null;
  lastSeenAt: string | null;
  lastCallAt: string | null;
  lastError: string | null;
  createdAt: string;
  /** The IP this number's browser goes out from, if one is assigned. */
  proxyId: string | null;
  proxyLabel: string | null;
  /** The saved browser profile (CloakBrowser): WhatsApp Web's login, and so on. version 0 = never saved. */
  profile: { version: number; bytes: number | null; savedAt: string | null };
  /**
   * The WhatsApp account its WhatsApp Web is actually logged in as (E.164),
   * as the worker last read it; null until read. Calls are refused while it
   * differs from `phone` — they would go out from the other number.
   */
  linkedPhone: string | null;
  /** The call worker keeping its WhatsApp Web open right now, if any (see WorkerLeaseRequest). */
  openOn: string | null;
};

/**
 * Linking WhatsApp Web on a station: the operator asks for it, a worker opens
 * the browser and shows the login screen; the operator types the 8-character
 * code into the phone's Linked devices (or scans the QR in the screenshot).
 */
export type StationLinkState = {
  requestedAt: string;
  /** "Log in with phone number" code, when the worker could read one. */
  code: string | null;
  /** PNG data URL of WhatsApp Web's login screen, so the QR or code is visible either way. */
  screenshot: string | null;
  updatedAt: string | null;
};

/** GET /api/calling/stations */
export type ListStationsResponse = { stations: CallingStation[] };

/** POST /api/calling/stations */
export type CreateStationRequest = {
  name: string;
  phone: string;
  launcher: StationLauncher;
  gologinProfileId?: string | null;
  proxyId?: string | null;
};

/** PATCH /api/calling/stations/:id — every field optional. */
export type UpdateStationRequest = {
  name?: string;
  /** E.164 — e.g. to match the account its WhatsApp Web turned out to be logged in as (linkedPhone). */
  phone?: string;
  launcher?: StationLauncher;
  gologinProfileId?: string | null;
  /** null takes the proxy away; a proxy belongs to at most one number. */
  proxyId?: string | null;
  /** Only active ⇄ paused from the app; the worker sets the rest. */
  status?: "active" | "paused";
};

/**
 * POST /api/calling/stations/:id/link — ask a worker to open WhatsApp Web's
 * login; body `{ fresh: true }` first discards the session it is logged in
 * with (the wrong account). DELETE cancels it.
 */
export type StartLinkRequest = { fresh?: boolean };

/** POST /api/calling/stations/:id/link — ask a worker to open WhatsApp Web's login. DELETE cancels it. */
export type StationResponse = { station: CallingStation };

// --- proxies: the IPs calling numbers go out from ---------------------------

export const PROXY_PROTOCOLS = ["http", "socks5"] as const;
export type ProxyProtocol = (typeof PROXY_PROTOCOLS)[number];

/**
 * One outbound IP (a static ISP / residential proxy) a calling number's
 * browser uses. Each belongs to at most one number, so numbers never share
 * an IP. The password is stored encrypted and never sent to the browser.
 */
export type CallingProxy = {
  id: string;
  label: string;
  protocol: ProxyProtocol;
  host: string;
  port: number;
  username: string | null;
  hasPassword: boolean;
  /** ISO 3166 alpha-2, e.g. "IN". */
  country: string | null;
  /** IANA zone the browser shows while using this IP, e.g. "Asia/Kolkata". */
  timezone: string | null;
  provider: string | null;
  notes: string | null;
  /** The number it is assigned to, if any. */
  stationId: string | null;
  stationName: string | null;
  createdAt: string;
};

/** GET /api/calling/proxies */
export type ListProxiesResponse = { proxies: CallingProxy[] };

/** POST /api/calling/proxies */
export type CreateProxyRequest = {
  label: string;
  protocol: ProxyProtocol;
  host: string;
  port: number;
  username?: string | null;
  password?: string | null;
  country?: string | null;
  timezone?: string | null;
  provider?: string | null;
  notes?: string | null;
};

/** PATCH /api/calling/proxies/:id — every field optional; an absent or empty password keeps the saved one. */
export type UpdateProxyRequest = Partial<CreateProxyRequest>;

/** POST/PATCH answer; DELETE answers { ok: true } (refused while a number uses it). */
export type ProxyResponse = { proxy: CallingProxy };

// --- the call worker's API (/api/call-worker/*, Bearer CALL_WORKER_SECRET) ---

/** POST /api/call-worker/claim */
export type WorkerClaimRequest = {
  /** A name for this worker, shown on the station while it holds it. */
  workerId: string;
  /** The launchers this worker can open; it is only given stations that use one of them. */
  launchers: StationLauncher[];
  /** Only these stations (a worker pinned to its numbers — e.g. one per container for TUNNEL); all when absent. */
  stations?: string[];
};

/**
 * POST /api/call-worker/leases — keep numbers' WhatsApp Web open. Sent every
 * LEASE_RENEW_MS: the worker names the stations it holds open (renewed) and
 * how many more it can hold; it is granted new ones up to `capacity` and told
 * which of its held ones to close (paused, logged out, moved to another
 * launcher, deleted). A lease not renewed for LEASE_TTL_MS lapses.
 */
export type WorkerLeaseRequest = {
  workerId: string;
  launchers: StationLauncher[];
  stations?: string[];
  /** The most stations this worker keeps open at once. */
  capacity: number;
  held: string[];
};
export type WorkerLeaseResponse = {
  /** Stations newly leased to this worker: open them. */
  granted: WorkerStation[];
  /** Held stations this worker must close: no longer to be kept open, or now someone else's. */
  release: string[];
};
export const LEASE_TTL_MS = 60_000;
export const LEASE_RENEW_MS = 20_000;

export type WorkerStation = {
  id: string;
  organizationId: string;
  name: string;
  phone: string;
  launcher: StationLauncher;
  gologinProfileId: string | null;
  /** The organization's GoLogin API token, for the gologin_* launchers. */
  gologinToken: string | null;
  /** The number's assigned proxy, password decrypted, or null to use the worker's own IP. */
  proxy: WorkerProxy | null;
  /** CloakBrowser's fingerprint seed for this number (10000–99999) — the database is its source of truth. */
  fingerprintSeed: number;
  /** The saved browser profile: its version and a short-lived download URL (null when never saved). */
  profile: { version: number; downloadUrl: string | null };
};

export type WorkerProxy = {
  /** "socks5://host:port" or "http://host:port". */
  server: string;
  username: string | null;
  password: string | null;
  timezone: string | null;
};

/** POST /api/call-worker/stations/:id/profile/upload-url — where to PUT the packed profile (tar.gz). */
export type WorkerProfileUploadRequest = { bytes: number };
export type WorkerProfileUploadResponse = { url: string; headers: Record<string, string>; key: string };

/**
 * POST /api/call-worker/stations/:id/profile — the upload is done; make it the
 * number's profile. Refused (409) unless `baseVersion` is still the current
 * version, so a stale worker never overwrites a newer profile.
 */
export type WorkerProfileCommitRequest = { key: string; bytes: number; baseVersion: number };
export type WorkerProfileCommitResponse = { version: number };

/** One AI call a worker runs on a station: an outbound call it claimed, or an incoming one it answers. */
export type WorkerCall = {
  id: string;
  /** E.164. */
  phone: string;
  /** The call's bearer token for /api/call-recorder/*, minted at claim (or answer) time. */
  recorderToken: string;
  lead: RecorderLead | null;
  brief: string;
  /** The agent's name and voice (null: the defaults in contract.ts). */
  agentName: string | null;
  agentVoice: string | null;
  /** The rep talks from AgentSDR instead of the agent; audio goes through AgentSDR's relay (contract.ts). */
  remoteRep: boolean;
};

export type WorkerJob =
  | {
      kind: "call";
      station: WorkerStation;
      call: WorkerCall;
    }
  | {
      kind: "link";
      station: WorkerStation;
      /**
       * Start from a logged-out browser: the session it holds is the wrong
       * WhatsApp account. The worker discards the saved session (the
       * fingerprint stays) before showing the login screen.
       */
      fresh: boolean;
    };

export type WorkerClaimResponse = { job: WorkerJob | null };

/** POST /api/call-worker/stations/:id/state — the worker's report on a station. */
export type WorkerStationStateRequest = {
  /** "logged_out" when WhatsApp Web shows its login screen; "active" once it shows the chats. */
  status?: "active" | "logged_out";
  /** While linking: the code and screenshot to show the operator. null clears them. */
  link?: { code: string | null; screenshot: string | null } | null;
  /** The link attempt is over (linked, or given up); clears the request. */
  linkDone?: boolean;
  error?: string | null;
  /** The account WhatsApp Web is logged in as (E.164), read whenever the worker finds it logged in. */
  linkedPhone?: string | null;
};

/**
 * One timed step of a cloud call. `at` is epoch milliseconds; `source` says
 * who saw it — the worker (claim, browser, WhatsApp loading) or the extension
 * in the station's browser (dialing, ringing, pick-up, the AI agent).
 */
export type CallTimelineEntry = { at: number; source: "worker" | "extension"; text: string };

/** POST /api/call-worker/calls/:id/timeline — replaces the call's timeline (sent as the call goes, and at its end). */
export type WorkerTimelineRequest = { entries: CallTimelineEntry[] };
export const MAX_TIMELINE_ENTRIES = 800;

/** POST /api/call-worker/calls/:id/release — the worker could not run the call; it is failed with `error`. */
export type WorkerReleaseRequest = { error: string };

/** GET /api/call-worker/calls/:id */
export type WorkerCallStatus = {
  status: "pending" | "in_progress" | "recorded" | "no_recording" | "failed";
  /** Terminal: the call is over and reported (recording uploaded, if any). */
  done: boolean;
};

// --- live phase of a cloud call --------------------------------------------

/** POST /api/call-recorder/calls/:id/phase — from the extension in station mode. */
export type RecorderPhaseRequest = { phase: RecorderCallPhase };

/** The phase a call is in before the extension reports any: queued for a worker, or its browser opening. */
export type CloudCallPhase =
  | { kind: "queued" }
  | { kind: "starting-browser" }
  | RecorderCallPhase;

// --- AgentSDR's own WhatsApp messaging through a station (no Unipile) -------
// A message to send is a station_message_jobs row (src/lib/whatsapp/
// stationMessaging.ts). Only the worker holding the station's lease (its
// WhatsApp Web kept open) claims it, and only while the station has no open
// call; a station with a claimed message is not given a call. The worker
// sends it through the extension (agentsdrStation.sendMessage) and reports
// the result. It also reads what arrives on the number
// (agentsdrStation.takeInbound) and posts it to /stations/:id/inbound.

/** POST /api/call-worker/messages/claim — the next message for one of `stations`. */
export type WorkerMessageClaimRequest = {
  workerId: string;
  /** Stations this worker holds open (leased) with no call running on them now. */
  stations: string[];
};

export type WorkerMessageJob = {
  id: string;
  stationId: string;
  /** E.164. */
  phone: string;
  body: string;
};

export type WorkerMessageClaimResponse = { job: WorkerMessageJob | null };

/**
 * POST /api/call-worker/messages/:id/result. `retryable`: nothing reached
 * WhatsApp (a call started on the page, WhatsApp Web was not ready) — the job
 * goes back to the queue once, then fails.
 */
export type WorkerMessageResultRequest =
  | { ok: true; providerMessageId: string | null; sentAt: number }
  /** `uncertain`: it may have gone out (Send was pressed, nothing confirmed it): never resent, kept as "uncertain". */
  | { ok: false; error: string; retryable?: boolean; uncertain?: boolean };

/**
 * A claimed message job whose worker went quiet this long is failed as
 * uncertain — never requeued, since it may have gone out. (Only an explicit
 * retryable failure from the worker requeues a job, once.)
 */
export const MESSAGE_CLAIM_STALE_MS = 2 * 60 * 1000;
/** A queued message no worker claimed in this long is failed: no worker has its number open. */
export const MESSAGE_QUEUED_EXPIRES_MS = 30 * 60 * 1000;

/**
 * A message WhatsApp Web showed on a station's number: one from the lead
 * (inbound), or one sent from the number (outbound — typed on the phone, or
 * the echo of AgentSDR's own send).
 */
export type StationInboundMessage = {
  /**
   * WhatsApp's id for the message as the extension read it — msg.id._serialized
   * ("false_<chat jid>_<key id>") or a DOM row's data-id (same format), or the
   * key id alone. The server keys on the key id.
   */
  providerMessageId: string;
  /** The other side's number, E.164, when known (a "@lid" chat may not tell). */
  chatPhone: string | null;
  /** The chat's WhatsApp id: "<digits>@c.us", "<digits>@s.whatsapp.net" or "<id>@lid". Groups are never sent. */
  chatJid: string;
  /** The contact's name or push name as WhatsApp shows it. */
  chatName: string | null;
  direction: "inbound" | "outbound";
  /** The text (a caption for media); "" for a message with none. */
  text: string;
  /** Epoch milliseconds. */
  sentAt: number;
  /** WhatsApp's message type when not plain text ("image", "ptt", "document", …). */
  kind?: string | null;
};

/** Where the extension read the messages from: WhatsApp's own message store, the DOM, or nothing works. */
export type StationInboundSource = "store" | "dom" | "none";

/** POST /api/call-worker/stations/:id/inbound */
export type WorkerInboundRequest = { source: StationInboundSource; messages: StationInboundMessage[] };
export type WorkerInboundResponse = { stored: number; skipped: number };
export const MAX_INBOUND_BATCH = 100;

/** agentsdrStation.sendMessage — the extension's answer. */
export type StationSendResult =
  | { ok: true; providerMessageId: string | null }
  | { ok: false; error: string; retryable: boolean; uncertain?: boolean };

/** agentsdrStation.takeInbound — what arrived since the last take. */
export type StationInboundTake = { source: StationInboundSource; messages: StationInboundMessage[] };

// --- incoming calls: the AI answers a lead who calls a station back ---------
//
// The extension (0.22.0+, station mode only) notices a WhatsApp call ringing
// on the number and keeps it for the worker, which polls
// agentsdrStation.takeIncomingCalls() about once a second on each open, idle
// number and asks AgentSDR whether to answer. AgentSDR answers only a known
// lead (Person) who is not Do Not Contact, on a number that is free, at any
// hour; anything else rings out. When it answers it creates the call's
// call_sessions row (direction 'inbound', already claimed by this worker) and
// the worker hands it to agentsdrStation.answerCall(), after which it is the
// outbound call's path: recording, the agent, the upload, the transcript.

/** A WhatsApp call ringing on a station's number, as the extension saw it. */
export type StationIncomingCall = {
  /** WhatsApp's id for the call, so one ring is handled once. */
  waCallId: string;
  /** The caller's number, E.164, or null when WhatsApp did not reveal it (an unresolved "@lid"). */
  phone: string | null;
  /** The caller's WhatsApp name, when shown. */
  callerName: string | null;
  isVideo: boolean;
  isGroup: boolean;
  /** When it started ringing (ms). */
  at: number;
};

/** POST /api/call-worker/stations/:id/incoming */
export type WorkerIncomingCallRequest = { workerId: string; call: StationIncomingCall };
export type WorkerIncomingCallResponse =
  | { answer: true; call: WorkerCall }
  | { answer: false; reason: string };

/** A ring older than this is not answered: WhatsApp gives up on a call after about 45 s. */
export const INCOMING_CALL_MAX_AGE_MS = 30_000;
