import type { ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";
import { chromium, type Browser, type BrowserContext } from "playwright-core";
import type { WorkerStation } from "../../../src/lib/calls/stationContract";
import { config } from "./config";
import { purgeServiceWorkers, resetProfile, restoreProfile, saveProfile } from "./profiles";
import { log } from "./log";
import { startProxyRelay, type ProxyRelay } from "./proxyRelay";

export type StationBrowser = { context: BrowserContext; close(): Promise<void> };

/**
 * A plain desktop Chrome user agent for the bundled Chromium. Headless
 * Chromium says "HeadlessChrome", and WhatsApp Web answers that with its
 * "works with Google Chrome 100+" page instead of loading (seen 11 Oct 2026).
 */
function desktopUserAgent(): string {
  let version = "140.0.0.0";
  try {
    const browsers = JSON.parse(readFileSync(createRequire(import.meta.url).resolve("playwright-core/browsers.json"), "utf8")) as {
      browsers: { name: string; browserVersion?: string }[];
    };
    const major = browsers.browsers.find((b) => b.name === "chromium")?.browserVersion?.split(".")[0];
    if (major) version = `${major}.0.0.0`;
  } catch {
    // Keep the fallback version; any recent one passes WhatsApp's check.
  }
  const platform =
    process.platform === "darwin"
      ? "Macintosh; Intel Mac OS X 10_15_7"
      : process.platform === "win32"
        ? "Windows NT 10.0; Win64; x64"
        : "X11; Linux x86_64";
  return `Mozilla/5.0 (${platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${version} Safari/537.36`;
}

/** Flags shared by every launcher: fake media devices and no background throttling. */
export function chromiumArgs(extensionPath: string): string[] {
  return [
    `--disable-extensions-except=${extensionPath}`,
    `--load-extension=${extensionPath}`,
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-blink-features=AutomationControlled",
    "--lang=en-US",
  ];
}

const CLOUD_START_ATTEMPTS = 3;

/** An error's first line — Playwright appends its whole call log to the message. */
export function firstLine(error: unknown): string {
  const text = (error instanceof Error ? error.message : String(error)).split("\n")[0]!;
  // Node's fetch says only "fetch failed"; the reason (DNS, refused, TLS,
  // timeout, and the host) is on its cause — the one useful part.
  const cause = error instanceof Error ? (error.cause as { code?: string; message?: string; hostname?: string } | undefined) : undefined;
  const reason = cause ? [cause.code, cause.hostname, cause.message].filter(Boolean).join(" ") : "";
  return (reason && !text.includes(reason) ? `${text} (${reason})` : text).slice(0, 300);
}

/**
 * `fresh`: open logged out, discarding the session the profile holds (see WorkerJob "link").
 * `note`: receives the launcher's own timed steps (GoLogin's start-up phases), for the call's timeline.
 */
export async function openStationBrowser(
  station: WorkerStation,
  options: { fresh?: boolean; note?: (text: string) => void } = {},
): Promise<StationBrowser> {
  timingSink = options.note ?? null;
  switch (station.launcher) {
    case "cloak":
      return openCloak(station, options.fresh === true);
    case "local":
      if (options.fresh) await rm(join(config().profilesDir, station.id), { recursive: true, force: true });
      return openLocal(station);
    case "gologin_cloud":
      return openGologinCloud(station);
    case "gologin_sdk":
      return openGologinSdk(station);
    default:
      throw new Error(`Unknown launcher "${String(station.launcher)}" for station ${station.name}`);
  }
}

async function openLocal(station: WorkerStation): Promise<StationBrowser> {
  const cfg = config();
  await purgeServiceWorkers(join(cfg.profilesDir, station.id));
  // Playwright's own --mute-audio stays: nobody listens at a station, and
  // the extension taps WhatsApp's audio before the speakers.
  const ignoreDefaultArgs = ["--enable-automation", "--disable-extensions"];
  const context = await chromium.launchPersistentContext(join(cfg.profilesDir, station.id), {
    headless: cfg.headless,
    // The default headless shell cannot load extensions; "chromium" is the full build in new headless mode.
    channel: cfg.chromiumPath ? undefined : "chromium",
    viewport: cfg.headless ? { width: 1280, height: 900 } : null,
    userAgent: desktopUserAgent(),
    executablePath: cfg.chromiumPath,
    args: chromiumArgs(cfg.extensionPath),
    ignoreDefaultArgs,
    permissions: ["microphone"],
  });
  await context.grantPermissions(["microphone"], { origin: "https://web.whatsapp.com" });
  return { context, close: () => context.close() };
}

/**
 * CloakBrowser — stealth Chromium with C++-level fingerprint patches — on the
 * worker's own disk, one profile folder per station. The folder is the
 * station's whole state: WhatsApp Web's login, cookies and storage are saved
 * when the browser closes and loaded on the next open, and CloakBrowser keeps
 * the profile's fingerprint seed in it (`.cloakbrowser-seed`), so a number
 * shows the same device on every call. Measured 23 Oct 2026: opens in under
 * a second, WhatsApp Web loads headless, same seed and canvas across launches.
 *
 * The free binary runs one session at a time (a Pro key, in
 * CLOAKBROWSER_LICENSE_KEY, lifts that); the worker runs one job at a time.
 */
async function openCloak(station: WorkerStation, fresh: boolean): Promise<StationBrowser> {
  const cfg = config();
  const dir = join(cfg.profilesDir, "cloak", station.id);
  // The browser reaches the number's proxy through a local, password-free
  // relay: neither SOCKS5 nor Playwright's HTTP proxy auth works with the
  // proxies we buy (see proxyRelay.ts).
  const relay = station.proxy ? await startProxyRelay(station.proxy) : null;
  if (relay) {
    // Fail with the proxy's own reason now, not a browser error later.
    await relay.check().catch(async (error: unknown) => {
      await relay.close();
      throw new Error(`This number's IP doesn't work: ${error instanceof Error ? error.message : String(error)}`);
    });
  }
  // The saved profile and the number's fingerprint seed, from AgentSDR — or,
  // for a fresh link, only the seed.
  if (fresh) await resetProfile(station, dir);
  else await restoreProfile(station, dir);
  await purgeServiceWorkers(dir);
  const { launchPersistentContext } = await import("cloakbrowser");
  const context = await launchPersistentContext({
    userDataDir: dir,
    headless: cfg.headless,
    extensionPaths: [cfg.extensionPath],
    locale: cfg.cloakLocale,
    // The browser's clock follows the number's IP when it has one.
    timezone: station.proxy?.timezone ?? cfg.cloakTimezone,
    // Only WhatsApp needs the number's IP; see proxyBypass.
    ...(relay ? { proxy: { server: relay.server, bypass: proxyBypass(cfg.agentsdrUrl) } } : {}),
    // Media and throttling flags only: CloakBrowser supplies its own stealth
    // and extension flags, and our user agent and automation tweaks would
    // contradict its fingerprint.
    args: [
      ...chromiumArgs(cfg.extensionPath).filter(
        (arg) =>
          !arg.startsWith("--load-extension") &&
          !arg.startsWith("--disable-extensions-except") &&
          !arg.startsWith("--lang=") &&
          !arg.startsWith("--disable-blink-features"),
      ),
      // Nobody listens at a station: WhatsApp's playback of the lead stays off
      // the machine's speakers (the extension taps it before the output).
      "--mute-audio",
      // Call audio is UDP, which no browser proxy carries. Forcing it
      // through the proxy anyway (disable_non_proxied_udp) killed the audio
      // both ways while the call itself connected (23 Oct 2026), so it is
      // opt-in: STRICT_PROXY_UDP=true keeps the real IP hidden at the cost
      // of the call's audio, until a full tunnel carries UDP.
      ...(relay && cfg.strictProxyUdp ? ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"] : []),
    ],
  }).catch(async (error: unknown) => {
    await relay?.close();
    throw error;
  });
  await context.grantPermissions(["microphone"], { origin: "https://web.whatsapp.com" }).catch(() => {});
  return {
    context,
    close: async () => {
      await context.close();
      if (relay) logProxyUsage(station, relay);
      await relay?.close();
      // Only once closed: the profile is consistent on disk then.
      await saveProfile(station, dir);
    },
  };
}

/**
 * What goes direct instead of through the number's proxy. The proxy is there
 * so WhatsApp sees the number's IP; nothing else needs it, and the proxy is
 * billed by the GB. The AI's audio (Gemini Live, about 4 MB a minute) and the
 * recording's upload to R2 were most of a call's proxy traffic. A rep call's
 * audio goes to and from AgentSDR itself (its relay), so it is direct too.
 *
 * Loopback must be listed: Playwright otherwise proxies even localhost
 * (`<-loopback>`), and the extension's reports to a local AgentSDR went to the
 * proxy and were lost — the AI never got its token (23 Oct 2026).
 */
function directHosts(agentsdrUrl: string): string[] {
  return [
    "localhost",
    "127.0.0.1",
    "[::1]",
    new URL(agentsdrUrl).hostname,
    "generativelanguage.googleapis.com",
    "*.r2.cloudflarestorage.com",
    // WhatsApp Web's app files — the same public bundle for everyone, 98% of
    // a load's bytes (6 MB). GoLogin's SDK empties the browser cache when it
    // saves a profile, so every call fetched them again through the number's
    // home proxy: 20–60 s before the call could start, sometimes past the
    // 2-minute limit ("did not load in time", 23 Oct 2026). The account's own
    // connection (web.whatsapp.com, its /ws/chat socket) stays on the proxy.
    "static.whatsapp.net",
  ];
}

function proxyBypass(agentsdrUrl: string): string {
  return directHosts(agentsdrUrl).join(",");
}

const megabytes = (bytes: number) => `${(bytes / 1_048_576).toFixed(1)} MB`;

/** What this session cost on the number's proxy, which the provider bills by the GB. */
function logProxyUsage(station: WorkerStation, relay: ProxyRelay): void {
  const { total, byHost } = relay.usage();
  const top = [...byHost.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([host, bytes]) => `${host} ${megabytes(bytes)}`)
    .join(", ");
  log(`proxy @ ${station.name}: ${megabytes(total)} through the proxy (${top || "nothing"})`);
}

async function openGologinCloud(station: WorkerStation): Promise<StationBrowser> {
  if (!station.gologinToken) throw new Error(`Station ${station.name}: the organization has no GoLogin API token`);
  if (!station.gologinProfileId) throw new Error(`Station ${station.name}: no GoLogin profile id`);
  const url = `wss://cloudbrowser.gologin.com/connect?token=${encodeURIComponent(station.gologinToken)}&profile=${encodeURIComponent(station.gologinProfileId)}`;
  const token = station.gologinToken;
  const profileId = station.gologinProfileId;
  // Disconnecting does not stop a cloud profile: GoLogin keeps it running
  // (and billing hours) until it idles out, seen still "running" after a
  // job on 12 Oct 2026. So every close also stops it through the API.
  const stop = async () => {
    const response = await fetch(`https://api.gologin.com/browser/${encodeURIComponent(profileId)}/web`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }).catch((error: unknown) => {
      throw new Error(`could not stop the GoLogin cloud profile: ${String(error)}`);
    });
    if (!response.ok && response.status !== 404) throw new Error(`GoLogin refused to stop the cloud profile (HTTP ${response.status})`);
  };
  // GoLogin answers "503 Failed to start browser" while a profile is still
  // stopping from its last session (seen 12 Oct 2026, seconds after a stop);
  // it starts on a retry a few seconds later.
  let browser: Browser | null = null;
  for (let attempt = 1; !browser; attempt++) {
    try {
      browser = await chromium.connectOverCDP(url);
    } catch (error) {
      const busy = /\b503\b|failed to start browser/i.test(String(error));
      if (!busy || attempt >= CLOUD_START_ATTEMPTS) {
        await stop().catch(() => {});
        throw new Error(busy ? "GoLogin's cloud could not start this profile's browser (503) — try again in a minute" : firstLine(error));
      }
      await new Promise((resolve) => setTimeout(resolve, attempt * 5_000));
    }
  }
  const connected = browser;
  const context = connected.contexts()[0];
  if (!context) {
    await connected.close().catch(() => {});
    await stop().catch(() => {});
    throw new Error("GoLogin cloud browser opened without a browser context");
  }
  await context.grantPermissions(["microphone"], { origin: "https://web.whatsapp.com" }).catch(() => {});
  return {
    context,
    close: async () => {
      await connected.close().catch(() => {});
      await stop();
    },
  };
}

/** Where GoLogin's own start-up timings go while a browser opens (see hookGologinTimings). */
let timingSink: ((text: string) => void) | null = null;
let gologinTimingsHooked = false;

/**
 * The SDK times each start-up phase (getProfile, initProfileStorage — the
 * profile download — spawnBrowser, …) through the `debug` package, off by
 * default. Enabled here with its output redirected: only the "[timing]" lines
 * are kept, for the call's timeline; the SDK's other debug lines (one prints
 * the API token) are dropped, never printed.
 */
function hookGologinTimings(): void {
  if (gologinTimingsHooked) return;
  gologinTimingsHooked = true;
  const debug = createRequire(import.meta.url)("debug") as { enable(namespaces: string): void; log: (...args: unknown[]) => void };
  debug.log = (...args: unknown[]) => {
    const match = /\[timing\] ([\w ]+): (\d+)ms/.exec(args.map(String).join(" "));
    if (match) timingSink?.(`GoLogin ${match[1]}: ${match[2]} ms`);
  };
  debug.enable("gologin");
}

/**
 * The GoLogin SDK, fixed in two places for WhatsApp Web (gologin 3.0.6, 23 Oct 2026):
 *
 * - Before it uploads a profile, `sanitizeProfile()` deletes `Default/IndexedDB`,
 *   and the archiver leaves it out of the zip again, neither with an option to
 *   keep it — and IndexedDB is where WhatsApp Web keeps its login keys. Every
 *   open after a successful link came up with the account remembered but its
 *   keys gone; WhatsApp's server refused the session (400) and WhatsApp logged
 *   itself out (`?post_logout=1`). IndexedDB is set aside while the SDK
 *   sanitizes and added back into the zip it uploads.
 * - `stop()` never stops the browser: it uploads the profile and returns, and
 *   Playwright's close() of a CDP-connected browser only disconnects. Every
 *   job left an Orbita running, logged in, while its profile was uploaded
 *   mid-write. The browser is closed (CDP Browser.close, then a kill) and
 *   waited for before the upload.
 */
async function openGologinSdk(station: WorkerStation): Promise<StationBrowser> {
  if (!station.gologinToken) throw new Error(`Station ${station.name}: the organization has no GoLogin API token`);
  if (!station.gologinProfileId) throw new Error(`Station ${station.name}: no GoLogin profile id`);
  const cfg = config();
  // Dynamic import so the local launcher works without the gologin package loaded.
  hookGologinTimings();
  const { GoLogin } = await import("gologin");
  type Sdk = InstanceType<typeof GoLogin> & { sanitizeProfile(): Promise<void>; processSpawned?: ChildProcess | null };
  const baseSanitize = (GoLogin.prototype as unknown as Sdk).sanitizeProfile;
  type Zip = { addLocalFolder(localPath: string, zipPath: string): void; toBuffer(): Buffer };
  const AdmZip = createRequire(import.meta.url)("adm-zip") as new (input?: Buffer) => Zip;
  const baseZip = (GoLogin.prototype as unknown as { getProfileDataToUpdate(): Promise<Buffer> }).getProfileDataToUpdate;
  const baseSpawn = (GoLogin.prototype as unknown as { spawnBrowser(): Promise<unknown> }).spawnBrowser;
  class WhatsAppGoLogin extends GoLogin {
    /**
     * Only WhatsApp goes through the profile's proxy (see directHosts). On the
     * server, the AI's audio went Austria → an Indian home connection → Google
     * and back on every reply — a lag the lead heard (23 Oct 2026) — and used
     * the proxy's paid GB. GoLogin also maps every hostname to 0.0.0.0 but the
     * proxy's (--host-resolver-rules), so a bypassed host could not even
     * resolve; its rules are repeated with the direct hosts excluded, and the
     * later switch wins.
     */
    async spawnBrowser(): Promise<unknown> {
      const sdk = this as unknown as { proxy?: { host?: string } | null; extra_params?: string[] };
      const proxyHost = sdk.proxy?.host;
      if (proxyHost) {
        const direct = directHosts(cfg.agentsdrUrl);
        // Orbita 135+ takes its proxy from the profile's Preferences (written
        // by the SDK just before this), not from --proxy-server, so
        // --proxy-bypass-list alone did nothing; the pref's own bypass_list does.
        const prefsPath = join(this.profilePath(), "Default", "Preferences");
        const prefs = JSON.parse(await readFile(prefsPath, "utf8").catch(() => "{}")) as { proxy?: { mode?: string; bypass_list?: string } };
        if (prefs.proxy?.mode === "fixed_servers") {
          prefs.proxy.bypass_list = direct.join(";");
          await writeFile(prefsPath, JSON.stringify(prefs));
        }
        sdk.extra_params = [
          ...(sdk.extra_params ?? []).filter((a) => !a.startsWith("--proxy-bypass-list=") && !a.startsWith("--host-resolver-rules=")),
          `--proxy-bypass-list=${direct.join(";")}`,
          `--host-resolver-rules=MAP * 0.0.0.0 , EXCLUDE ${proxyHost} , EXCLUDE api.gologin.com , ${direct.map((h) => `EXCLUDE ${h}`).join(" , ")}`,
        ];
      }
      return baseSpawn.call(this);
    }


    /** The archiver drops IndexedDB from the upload too (a hard-coded list); put it back. */
    async getProfileDataToUpdate(): Promise<Buffer> {
      const zip = new AdmZip(await baseZip.call(this));
      const indexedDb = join(this.profilePath(), "Default", "IndexedDB");
      if (await stat(indexedDb).then((s) => s.isDirectory(), () => false)) zip.addLocalFolder(indexedDb, "Default/IndexedDB");
      return zip.toBuffer();
    }

    async sanitizeProfile(): Promise<void> {
      const indexedDb = join(this.profilePath(), "Default", "IndexedDB");
      const aside = join(this.profilePath(), "agentsdr-indexeddb");
      const kept = await rename(indexedDb, aside).then(() => true, () => false);
      try {
        await baseSanitize.call(this as unknown as Sdk);
      } finally {
        if (kept) await rename(aside, indexedDb);
      }
    }
  }
  const extra = chromiumArgs(cfg.extensionPath).filter((a) => !a.startsWith("--lang=") && !a.startsWith("--disable-extensions-except="));
  if (cfg.headless) extra.push("--headless=new");
  // In Docker the worker is root, and Chromium refuses to start as root
  // without --no-sandbox: Orbita exited at once and the SDK's wait for it
  // failed "ECONNREFUSED 127.0.0.1:<port>" (23 Oct 2026). /dev/shm in a
  // container is 64 MB unless raised.
  if (process.platform === "linux" && process.getuid?.() === 0) extra.push("--no-sandbox", "--disable-dev-shm-usage");
  const gl = new WhatsAppGoLogin({
    token: station.gologinToken,
    profile_id: station.gologinProfileId,
    // GoLogin merges a "--load-extension=" entry in extra_params with the extensions it installs itself.
    extra_params: extra,
    executablePath: cfg.chromiumPath,
  }) as unknown as Sdk;
  let browser: Browser | null = null;
  // The SDK discards Orbita's output; kept here so a browser that dies on
  // start says why (a missing library, the sandbox) instead of only that
  // nothing answered on its debugging port.
  let orbitaOutput = "";
  const watchOrbita = setInterval(() => {
    const child = gl.processSpawned;
    if (!child?.stderr) return;
    clearInterval(watchOrbita);
    child.stderr.on("data", (chunk: Buffer) => {
      orbitaOutput = (orbitaOutput + String(chunk)).slice(-2_000);
    });
    child.on("exit", (code, signal) => {
      orbitaOutput += `\n[Orbita exited: ${code ?? signal}]`;
    });
  }, 50);
  const shutDown = async () => {
    clearInterval(watchOrbita);
    const pid = gl.processSpawned?.pid;
    if (browser) {
      // Browser.close shuts Orbita down cleanly, so IndexedDB is flushed to disk.
      const cdp = await browser.newBrowserCDPSession().catch(() => null);
      await cdp?.send("Browser.close").catch(() => {});
      await browser.close().catch(() => {});
    }
    if (pid && !(await exited(pid, 10_000))) {
      process.kill(pid, "SIGKILL");
      await exited(pid, 5_000);
    }
    const stopAt = Date.now();
    await gl.stop();
    timingSink?.(`GoLogin profile uploaded in ${Date.now() - stopAt} ms`);
  };
  try {
    const startedAt = Date.now();
    const { wsUrl } = await gl.start();
    if (!wsUrl) throw new Error("GoLogin started the profile but gave no websocket URL");
    timingSink?.(`GoLogin profile started in ${Date.now() - startedAt} ms`);
    browser = await chromium.connectOverCDP(wsUrl);
    timingSink?.("connected to Orbita (CDP)");
    const context = browser.contexts()[0];
    if (!context) throw new Error("GoLogin browser has no browser context");
    await context.grantPermissions(["microphone"], { origin: "https://web.whatsapp.com" }).catch(() => {});
    return { context, close: shutDown };
  } catch (err) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const output = orbitaOutput.trim().split("\n").slice(-6).join(" | ");
    await shutDown().catch(() => {});
    if (output) throw new Error(`${firstLine(err)} — Orbita said: ${output}`.slice(0, 1_500));
    throw err;
  }
}

/** Waits up to `timeoutMs` for process `pid` to be gone. */
async function exited(pid: number, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      process.kill(pid, 0);
    } catch {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}
