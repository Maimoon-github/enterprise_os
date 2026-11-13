import { lookup as dnsLookup } from "node:dns/promises";
import { isIP } from "node:net";
import type { CellResult, CellValues, HttpConfig } from "../types";
import {
  PermanentRunError,
  pluck,
  tokensIn,
  type ColumnRunner,
} from "./types";

/** Response bodies past this are truncated before being stored as audit. */
const MAX_AUDIT_BYTES = 16 * 1024;

/** Redirect hops followed (each re-checked against the address block-list). */
const MAX_REDIRECTS = 3;

/**
 * An HTTP column may only read credentials from env vars with this prefix.
 * Without the restriction a member could name DATABASE_URL or
 * INTEGRATION_CREDENTIALS_KEY and have it sent to a URL they control.
 */
export const HTTP_SECRET_ENV_PREFIX = "GRID_HTTP_SECRET_";

export function isAllowedHttpSecretEnvVar(name: string): boolean {
  return /^GRID_HTTP_SECRET_[A-Z0-9_]+$/.test(name);
}

// ---------------------------------------------------------------------------
// SSRF guard
// ---------------------------------------------------------------------------

function ipv4Octets(ip: string): number[] | null {
  const parts = ip.split(".");
  if (parts.length !== 4) return null;
  const octets = parts.map((p) => (/^\d{1,3}$/.test(p) ? Number(p) : NaN));
  return octets.every((o) => o >= 0 && o <= 255) ? octets : null;
}

function isBlockedIpv4(octets: number[]): boolean {
  const [a, b, c] = octets;
  return (
    a === 0 || // 0.0.0.0/8 ("this network", 0.0.0.0 reaches localhost on Linux)
    a === 10 ||
    a === 127 ||
    (a === 100 && b >= 64 && b <= 127) || // CGNAT 100.64/10
    (a === 169 && b === 254) || // link-local, incl. cloud metadata
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 192 && b === 0 && c === 0) || // IETF protocol assignments
    (a === 198 && (b === 18 || b === 19)) || // benchmarking
    a >= 224 // multicast + reserved + broadcast
  );
}

/** Expands any textual IPv6 form to its eight 16-bit groups, or null. */
function ipv6Groups(ip: string): number[] | null {
  let text = ip.split("%")[0].toLowerCase(); // drop a zone id
  const dotted = text.match(/^(.*:)(\d+\.\d+\.\d+\.\d+)$/);
  if (dotted) {
    const v4 = ipv4Octets(dotted[2]);
    if (!v4) return null;
    text = `${dotted[1]}${((v4[0] << 8) | v4[1]).toString(16)}:${((v4[2] << 8) | v4[3]).toString(16)}`;
  }
  const halves = text.split("::");
  if (halves.length > 2) return null;
  const head = halves[0] ? halves[0].split(":") : [];
  const tail = halves.length === 2 && halves[1] ? halves[1].split(":") : [];
  const missing = 8 - head.length - tail.length;
  if (halves.length === 1 ? missing !== 0 : missing < 1) return null;
  const groups = [...head, ...Array(halves.length === 2 ? missing : 0).fill("0"), ...tail];
  const nums = groups.map((g) => (/^[0-9a-f]{1,4}$/.test(g) ? parseInt(g, 16) : NaN));
  return nums.length === 8 && nums.every((n) => !Number.isNaN(n)) ? nums : null;
}

/**
 * Whether a RESOLVED address is one a user-configured HTTP call must not reach:
 * loopback, private, link-local (cloud metadata), CGNAT, unspecified,
 * multicast/reserved, and IPv6 forms that embed an IPv4 address (mapped,
 * compatible, NAT64, 6to4). Anything unparseable is blocked.
 *
 * Call it on the addresses DNS returned, not on the hostname text: WHATWG
 * `new URL()` has already folded decimal/hex/short IPv4 spellings
 * ("2130706433", "0x7f.1") into dotted quads by then.
 */
export function isBlockedAddress(address: string): boolean {
  const ip = address.replace(/^\[|\]$/g, "");
  const version = isIP(ip.split("%")[0]);
  if (version === 4) {
    const octets = ipv4Octets(ip);
    return !octets || isBlockedIpv4(octets);
  }
  if (version === 6) {
    const g = ipv6Groups(ip);
    if (!g) return true;
    const embedded = (hi: number, lo: number) => isBlockedIpv4([hi >> 8, hi & 255, lo >> 8, lo & 255]);
    if (g.every((n) => n === 0)) return true; // ::
    if (g.slice(0, 7).every((n) => n === 0) && g[7] === 1) return true; // ::1
    if (g.slice(0, 5).every((n) => n === 0) && (g[5] === 0xffff || g[5] === 0)) return embedded(g[6], g[7]); // mapped / compatible
    if (g[0] === 0x64 && g[1] === 0xff9b && g.slice(2, 6).every((n) => n === 0)) return embedded(g[6], g[7]); // NAT64
    if (g[0] === 0x2002) return embedded(g[1], g[2]); // 6to4
    if ((g[0] & 0xfe00) === 0xfc00) return true; // fc00::/7 unique local
    if ((g[0] & 0xffc0) === 0xfe80) return true; // fe80::/10 link-local
    if ((g[0] & 0xff00) === 0xff00) return true; // multicast
    return false;
  }
  return true;
}

type Resolver = (hostname: string) => Promise<string[]>;

const resolveAll: Resolver = async (hostname) =>
  (await dnsLookup(hostname, { all: true, verbatim: true })).map((entry) => entry.address);

/**
 * Throws PermanentRunError unless every address the host resolves to is
 * public. Self-hosters calling internal services set GRID_HTTP_ALLOW_PRIVATE=true.
 *
 * Residual risk: fetch() resolves the name again, so a hostile DNS server
 * could answer differently the second time (rebinding). Closing that needs a
 * pinned dispatcher; this stops the direct and redirect-based cases.
 */
export async function assertPublicUrl(
  url: URL,
  resolve: Resolver = resolveAll,
  allowPrivate = process.env.GRID_HTTP_ALLOW_PRIVATE === "true",
): Promise<void> {
  if (allowPrivate) return;
  const host = url.hostname.replace(/^\[|\]$/g, "");
  let addresses: string[];
  if (isIP(host.split("%")[0])) {
    addresses = [host];
  } else {
    try {
      addresses = await resolve(host);
    } catch {
      throw new PermanentRunError(`Could not resolve host: ${host}`);
    }
  }
  if (!addresses.length || addresses.some(isBlockedAddress)) {
    throw new PermanentRunError(
      "That address is private or internal and cannot be called from a table. " +
        "Self-hosters can allow it with GRID_HTTP_ALLOW_PRIVATE=true.",
    );
  }
}

// ---------------------------------------------------------------------------
// Interpolation (context-aware escaping)
// ---------------------------------------------------------------------------

const TOKEN = /\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g;

function cellText(value: unknown): string {
  if (value === null || value === undefined) return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

/**
 * Fills a URL template. Values are percent-encoded so a cell holding
 * "a&admin=1" or "../x" cannot add parameters or path segments. A token that
 * opens the template is the origin itself ("{{website}}") and stays raw.
 */
export function interpolateUrl(template: string, row: CellValues): string {
  return template.replace(TOKEN, (_m, key: string, offset: number) => {
    const text = cellText(row[key]);
    return offset === 0 ? text : encodeURIComponent(text);
  });
}

/** Whether `index` falls inside a double-quoted JSON string literal. */
function insideJsonString(template: string, index: number): boolean {
  let inString = false;
  for (let i = 0; i < index; i += 1) {
    const ch = template[i];
    if (inString && ch === "\\") i += 1;
    else if (ch === '"') inString = !inString;
  }
  return inString;
}

/**
 * Fills a JSON body template. Inside a string literal the value is
 * JSON-escaped (a quote in a cell cannot close the string or inject keys).
 * Bare, a text value that is itself a JSON value ("42", "true", "[1,2]") is
 * inserted as that value — the way `{"n": {{count}}}` always behaved — any
 * other text becomes a quoted JSON string, and an empty one `null`.
 */
export function interpolateJsonBody(template: string, row: CellValues): string {
  return template.replace(TOKEN, (_m, key: string, offset: number) => {
    const value = row[key];
    if (insideJsonString(template, offset)) return JSON.stringify(cellText(value)).slice(1, -1);
    if (value === null || value === undefined || value === "") return "null";
    if (typeof value === "string") {
      try {
        return JSON.stringify(JSON.parse(value));
      } catch {
        return JSON.stringify(value);
      }
    }
    return cellText(value);
  });
}

function interpolateFormBody(template: string, row: CellValues): string {
  return template.replace(TOKEN, (_m, key: string) => encodeURIComponent(cellText(row[key])));
}

function interpolateRaw(template: string, row: CellValues): string {
  return template.replace(TOKEN, (_m, key: string) => cellText(row[key]));
}

/** Header values may not carry line breaks (header injection). */
export function stripLineBreaks(value: string): string {
  return value.replace(/[\r\n]+/g, " ").trim();
}

/** GET/HEAD are safe to repeat; anything else may already have taken effect. */
export function isIdempotentMethod(method: string): boolean {
  return method === "GET" || method === "HEAD";
}

/**
 * HTTP / REST columns — the universal escape hatch.
 *
 * The highest-leverage runner to build first: it lets a self-hoster wire up
 * any provider that was never built as a first-class integration. Integrations
 * added later are this same call with the credentials and URL filled in for
 * you, rather than a separate mechanism.
 */
export const httpRunner: ColumnRunner<HttpConfig> = {
  type: "http",

  resolveDeps(config) {
    const found = [...tokensIn(config.url), ...tokensIn(config.body)];
    for (const v of Object.values(config.headers ?? {})) found.push(...tokensIn(v));
    return [...new Set(found)];
  },

  async run(config, row, ctx): Promise<CellResult> {
    const url = interpolateUrl(config.url ?? "", row);
    if (!url) throw new PermanentRunError("This column has no URL configured");

    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      throw new PermanentRunError(`Not a valid URL after substitution: ${url}`);
    }
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      throw new PermanentRunError(`Unsupported protocol: ${parsed.protocol}`);
    }

    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries(config.headers ?? {})) {
      const name = stripLineBreaks(k);
      if (name) headers[name] = stripLineBreaks(interpolateRaw(v, row));
    }

    // The credential is read from the environment by NAME. It is never stored
    // in the database, because grid_providers rows end up in the dumps that
    // self-hosters share around. See docs/design/enrichment-plan.md §6.
    if (config.authEnvVar) {
      // Re-checked here, not only at save time: a config written before the
      // restriction (or straight into the database) must not read arbitrary env.
      if (!isAllowedHttpSecretEnvVar(config.authEnvVar)) {
        throw new PermanentRunError(
          `The credential env var must be named ${HTTP_SECRET_ENV_PREFIX}<NAME> (got ${config.authEnvVar})`,
        );
      }
      const secret = process.env[config.authEnvVar];
      if (!secret) {
        throw new PermanentRunError(
          `Environment variable ${config.authEnvVar} is not set on this server`,
        );
      }
      const value = stripLineBreaks(secret);
      headers.Authorization ??= value.startsWith("Bearer ") ? value : `Bearer ${value}`;
    }

    const method = (config.method ?? "GET").toUpperCase();
    const contentTypeKey = Object.keys(headers).find((k) => k.toLowerCase() === "content-type");
    const requestType = contentTypeKey ? headers[contentTypeKey].toLowerCase() : "application/json";
    const template = config.body ?? "";
    const body = method === "GET"
      ? undefined
      : (requestType.includes("json")
          ? interpolateJsonBody(template, row)
          : requestType.includes("x-www-form-urlencoded")
            ? interpolateFormBody(template, row)
            : interpolateRaw(template, row)) || undefined;
    if (body && !contentTypeKey) headers["Content-Type"] = "application/json";

    // Two timeouts are combined: the caller's per-cell budget, and this
    // request's own. Whichever fires first aborts the fetch.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ctx.timeoutMs);
    const onOuterAbort = () => controller.abort();
    ctx.signal?.addEventListener("abort", onOuterAbort);

    const started = Date.now();
    // Non-idempotent calls are never retried on a timeout, 5xx or network
    // error: the first attempt may already have taken effect (a charge, a
    // message). 429 means "not processed", so it stays retryable.
    const retryable = isIdempotentMethod(method);
    const failure = (message: string) => (retryable ? new Error(message) : new PermanentRunError(message));
    try {
      const res = await fetchFollowingRedirects(parsed, { method, headers, body }, controller.signal);
      const text = await res.text();

      let parsedBody: unknown = text;
      const contentType = res.headers.get("content-type") ?? "";
      if (contentType.includes("json") || text.trimStart().startsWith("{") || text.trimStart().startsWith("[")) {
        try {
          parsedBody = JSON.parse(text);
        } catch {
          // Leave it as text — a provider mislabelling its content type is
          // not worth failing the cell over.
        }
      }

      if (!res.ok) {
        // 4xx is the config being wrong and will fail identically on retry;
        // 5xx and 429 are worth retrying, so only the former is permanent.
        const snippet = text.slice(0, 200);
        const message = `${res.status} ${res.statusText}${snippet ? ` — ${snippet}` : ""}`;
        if (res.status >= 400 && res.status < 500 && res.status !== 429) {
          throw new PermanentRunError(message);
        }
        if (res.status === 429) throw Object.assign(new Error(message), { retryable: true });
        throw failure(message);
      }

      const value = pluck(parsedBody, config.responsePath);
      const empty = value === null || value === undefined || value === "";

      return {
        value: empty ? null : value,
        provider: config.providerKey,
        outcome: empty ? "miss" : "hit",
        // A miss still costs money at most providers, which is the whole
        // reason waterfall ordering is worth tuning.
        costCents: config.costCents ?? 0,
        latencyMs: Date.now() - started,
        request: { url, method },
        response: truncate(parsedBody),
      } as CellResult;
    } catch (err) {
      if (err instanceof PermanentRunError) throw err;
      if ((err as Error).name === "AbortError") {
        throw failure(`Request timed out after ${ctx.timeoutMs}ms`);
      }
      if ((err as { retryable?: boolean }).retryable) throw err;
      throw retryable ? err : new PermanentRunError(`Request failed: ${(err as Error).message}`);
    } finally {
      clearTimeout(timer);
      ctx.signal?.removeEventListener("abort", onOuterAbort);
    }
  },

  estimateCost(config) {
    return config.costCents ?? 0;
  },
};

/**
 * fetch() with manual redirect handling, so every hop is re-checked against
 * the address block-list. Credentials (headers, body) are dropped when a hop
 * changes origin, and a 301/302/303 becomes a body-less GET like a browser.
 */
async function fetchFollowingRedirects(
  first: URL,
  init: { method: string; headers: Record<string, string>; body?: string },
  signal: AbortSignal,
): Promise<Response> {
  let current = first;
  let { method, headers, body } = init;
  for (let hop = 0; ; hop += 1) {
    await assertPublicUrl(current);
    const res = await fetch(current, { method, headers, body, signal, redirect: "manual" });
    const location = res.headers.get("location");
    if (res.status < 300 || res.status >= 400 || !location) return res;
    if (hop >= MAX_REDIRECTS) throw new PermanentRunError(`Too many redirects (more than ${MAX_REDIRECTS})`);

    let next: URL;
    try {
      next = new URL(location, current);
    } catch {
      throw new PermanentRunError("The server redirected to an invalid URL");
    }
    if (next.protocol !== "https:" && next.protocol !== "http:") {
      throw new PermanentRunError(`Redirect to unsupported protocol: ${next.protocol}`);
    }
    if (next.origin !== current.origin) headers = {};
    if (res.status !== 307 && res.status !== 308) {
      method = "GET";
      body = undefined;
      headers = Object.fromEntries(
        Object.entries(headers).filter(([k]) => !/^content-(type|length)$/i.test(k)),
      );
    }
    current = next;
  }
}

/** Keeps one enormous response from bloating grid_cell_runs. */
function truncate(value: unknown): unknown {
  try {
    const json = JSON.stringify(value);
    if (json && json.length > MAX_AUDIT_BYTES) {
      return { truncated: true, preview: json.slice(0, MAX_AUDIT_BYTES) };
    }
    return value;
  } catch {
    return null;
  }
}
