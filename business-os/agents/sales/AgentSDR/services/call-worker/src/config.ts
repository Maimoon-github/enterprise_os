import { hostname, homedir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { STATION_LAUNCHERS, type StationLauncher } from "../../../src/lib/calls/stationContract";

function required(name: string): string {
  const v = process.env[name]?.trim();
  if (!v) throw new Error(`${name} is required`);
  return v;
}

function int(name: string, fallback: number): number {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) throw new Error(`${name} must be a positive number, got "${raw}"`);
  return n;
}

function launchers(): StationLauncher[] {
  const list = (process.env.LAUNCHERS ?? "local").split(",").map((s) => s.trim()).filter(Boolean);
  for (const l of list) {
    if (!(STATION_LAUNCHERS as readonly string[]).includes(l)) {
      throw new Error(`LAUNCHERS: unknown launcher "${l}" (expected ${STATION_LAUNCHERS.join(", ")})`);
    }
  }
  return list as StationLauncher[];
}

const here = dirname(fileURLToPath(import.meta.url));

export type Config = {
  agentsdrUrl: string;
  secret: string;
  workerId: string;
  launchers: StationLauncher[];
  extensionPath: string;
  profilesDir: string;
  headless: boolean;
  claimIntervalMs: number;
  callTimeoutMs: number;
  chromiumPath: string | undefined;
  /** CloakBrowser's time zone and language for every station it opens; match them to the IP the calls go out from. */
  cloakTimezone: string;
  cloakLocale: string;
  /** Keep WebRTC's UDP from leaving around a number's proxy (it then carries no call audio). */
  strictProxyUdp: boolean;
  /** How many numbers' WhatsApp Web this worker keeps open between calls (0: open a browser per call). */
  keepOpen: number;
  /** Only these stations (ids); every station when empty. */
  stations: string[];
  /** Gap between message claims when there is nothing to send (open numbers only). */
  messagePollMs: number;
  /** How often each open number's received messages are read and posted. */
  inboundPollMs: number;
  /** How often each open, idle number is checked for a call ringing on it (to be answered by the AI). */
  incomingPollMs: number;
};

export function loadConfig(): Config {
  return {
    agentsdrUrl: required("AGENTSDR_URL").replace(/\/+$/, ""),
    secret: required("CALL_WORKER_SECRET"),
    workerId: process.env.WORKER_ID?.trim() || hostname(),
    launchers: launchers(),
    extensionPath: resolve(process.env.EXTENSION_PATH?.trim() || join(here, "../../../extensions/whatsapp-recorder/dist")),
    profilesDir: resolve(process.env.PROFILES_DIR?.trim() || join(homedir(), ".agentsdr-call-worker", "profiles")),
    headless: process.env.HEADLESS?.trim().toLowerCase() === "true",
    claimIntervalMs: int("CLAIM_INTERVAL_MS", 1000),
    callTimeoutMs: int("CALL_TIMEOUT_MS", 30 * 60 * 1000),
    chromiumPath: process.env.CHROMIUM_PATH?.trim() || undefined,
    cloakTimezone: process.env.CLOAK_TIMEZONE?.trim() || "Asia/Kolkata",
    // English, which the extension needs: it finds WhatsApp's buttons by their English labels.
    cloakLocale: process.env.CLOAK_LOCALE?.trim() || "en-US",
    strictProxyUdp: process.env.STRICT_PROXY_UDP?.trim().toLowerCase() === "true",
    keepOpen: process.env.KEEP_OPEN?.trim() === "0" ? 0 : int("KEEP_OPEN", 0),
    stations: (process.env.STATIONS ?? "").split(",").map((s) => s.trim()).filter(Boolean),
    messagePollMs: int("MESSAGE_POLL_MS", 2000),
    inboundPollMs: int("INBOUND_POLL_MS", 10_000),
    incomingPollMs: int("INCOMING_POLL_MS", 1000),
  };
}

let cached: Config | null = null;
/** Read lazily so a module can be imported (e.g. by a test) before env is set. */
export function config(): Config {
  return (cached ??= loadConfig());
}

/** For tests and scripts that build their own config. */
export function setConfig(c: Config): void {
  cached = c;
}
