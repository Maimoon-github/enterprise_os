import "server-only";

import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { decryptCredentialText, encryptCredentialText } from "@/lib/integrations/credential-crypto";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import { callingProxies, callingStations } from "./schema";
import { CallApiError } from "./sessions";
import {
  PROXY_PROTOCOLS,
  type CallingProxy,
  type CreateProxyRequest,
  type ProxyProtocol,
  type UpdateProxyRequest,
  type WorkerProxy,
} from "./stationContract";

/**
 * The outbound IPs calling numbers go out from (static ISP / residential
 * proxies), one list per organization. A number names its proxy by id
 * (calling_stations.proxy_id, unique), so numbers never share an IP. The
 * password is encrypted with the integrations' credential key and only ever
 * decrypted for the call worker (workerProxy).
 */

type ProxyRow = typeof callingProxies.$inferSelect;

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const HOST_PATTERN = /^[a-z0-9.-]+$/i;

function toCallingProxy(row: ProxyRow, station: { id: string; name: string } | null): CallingProxy {
  return {
    id: row.id,
    label: row.label,
    protocol: row.protocol,
    host: row.host,
    port: row.port,
    username: row.username,
    hasPassword: Boolean(row.passwordEncrypted),
    country: row.country,
    timezone: row.timezone,
    provider: row.provider,
    notes: row.notes,
    stationId: station?.id ?? null,
    stationName: station?.name ?? null,
    createdAt: row.createdAt.toISOString(),
  };
}

export async function listProxies(): Promise<CallingProxy[]> {
  const rows = await db
    .select({ proxy: callingProxies, stationId: callingStations.id, stationName: callingStations.name })
    .from(callingProxies)
    .leftJoin(callingStations, and(eq(callingStations.proxyId, callingProxies.id), inOrg(callingStations)))
    .where(inOrg(callingProxies))
    .orderBy(asc(callingProxies.createdAt));
  return rows.map((row) =>
    toCallingProxy(row.proxy, row.stationId && row.stationName ? { id: row.stationId, name: row.stationName } : null),
  );
}

/** A proxy of this organization, or a 404 — also how a number's proxyId is checked. */
export async function requireProxy(id: string): Promise<ProxyRow> {
  if (!UUID_PATTERN.test(id)) throw new CallApiError(404, "IP not found");
  const [row] = await db.select().from(callingProxies).where(and(inOrg(callingProxies), eq(callingProxies.id, id))).limit(1);
  if (!row) throw new CallApiError(404, "IP not found");
  return row;
}

async function proxyView(row: ProxyRow): Promise<CallingProxy> {
  const [station] = await db
    .select({ id: callingStations.id, name: callingStations.name })
    .from(callingStations)
    .where(and(inOrg(callingStations), eq(callingStations.proxyId, row.id)))
    .limit(1);
  return toCallingProxy(row, station ?? null);
}

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new CallApiError(400, "Expected a JSON object");
  return value as Record<string, unknown>;
}

function optionalText(value: unknown, label: string, max: number): string | null {
  if (value == null || value === "") return null;
  if (typeof value !== "string") throw new CallApiError(400, `${label} must be text`);
  const text = value.trim();
  if (text.length > max) throw new CallApiError(400, `${label} is over ${max} characters`);
  return text || null;
}

function parseLabel(value: unknown): string {
  const label = optionalText(value, "Label", 80);
  if (!label) throw new CallApiError(400, "Give the IP a label");
  return label;
}

function parseProtocol(value: unknown): ProxyProtocol {
  if (typeof value === "string" && (PROXY_PROTOCOLS as readonly string[]).includes(value)) return value as ProxyProtocol;
  throw new CallApiError(400, `protocol must be one of ${PROXY_PROTOCOLS.join(", ")}`);
}

function parseHost(value: unknown): string {
  const host = optionalText(value, "Host", 255);
  if (!host || !HOST_PATTERN.test(host)) throw new CallApiError(400, "Host must be a hostname or IP address");
  return host;
}

function parsePort(value: unknown): number {
  const port = typeof value === "string" ? Number(value) : value;
  if (typeof port !== "number" || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new CallApiError(400, "Port must be a number from 1 to 65535");
  }
  return port;
}

function parseCountry(value: unknown): string | null {
  const country = optionalText(value, "Country", 2);
  if (country && !/^[a-z]{2}$/i.test(country)) throw new CallApiError(400, "Country must be a two-letter code, e.g. IN");
  return country?.toUpperCase() ?? null;
}

function parseTimezone(value: unknown): string | null {
  const zone = optionalText(value, "Time zone", 64);
  if (!zone) return null;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: zone });
  } catch {
    throw new CallApiError(400, `"${zone}" is not a time zone (e.g. Asia/Kolkata)`);
  }
  return zone;
}

export function parseCreateProxyRequest(value: unknown): CreateProxyRequest {
  const body = asObject(value);
  return {
    label: parseLabel(body.label),
    protocol: parseProtocol(body.protocol),
    host: parseHost(body.host),
    port: parsePort(body.port),
    username: optionalText(body.username, "Username", 200),
    password: optionalText(body.password, "Password", 500),
    country: parseCountry(body.country),
    timezone: parseTimezone(body.timezone),
    provider: optionalText(body.provider, "Provider", 80),
    notes: optionalText(body.notes, "Notes", 500),
  };
}

export function parseUpdateProxyRequest(value: unknown): UpdateProxyRequest {
  const body = asObject(value);
  const update: UpdateProxyRequest = {};
  if (body.label !== undefined) update.label = parseLabel(body.label);
  if (body.protocol !== undefined) update.protocol = parseProtocol(body.protocol);
  if (body.host !== undefined) update.host = parseHost(body.host);
  if (body.port !== undefined) update.port = parsePort(body.port);
  if (body.username !== undefined) update.username = optionalText(body.username, "Username", 200);
  // Absent or empty keeps the saved password, like every other secret field in Settings.
  if (typeof body.password === "string" && body.password.trim()) update.password = optionalText(body.password, "Password", 500);
  if (body.country !== undefined) update.country = parseCountry(body.country);
  if (body.timezone !== undefined) update.timezone = parseTimezone(body.timezone);
  if (body.provider !== undefined) update.provider = optionalText(body.provider, "Provider", 80);
  if (body.notes !== undefined) update.notes = optionalText(body.notes, "Notes", 500);
  return update;
}

export async function createProxy(input: CreateProxyRequest): Promise<CallingProxy> {
  const [row] = await db
    .insert(callingProxies)
    .values({
      organizationId: currentOrganizationId(),
      label: input.label,
      protocol: input.protocol,
      host: input.host,
      port: input.port,
      username: input.username ?? null,
      passwordEncrypted: input.password ? encryptCredentialText(input.password) : null,
      country: input.country ?? null,
      timezone: input.timezone ?? null,
      provider: input.provider ?? null,
      notes: input.notes ?? null,
    })
    .returning();
  if (!row) throw new Error("calling_proxies insert did not return a row");
  return toCallingProxy(row, null);
}

export async function updateProxy(id: string, input: UpdateProxyRequest): Promise<CallingProxy> {
  const current = await requireProxy(id);
  const { password, ...rest } = input;
  const [row] = await db
    .update(callingProxies)
    .set({ ...rest, ...(password ? { passwordEncrypted: encryptCredentialText(password) } : {}), updatedAt: new Date() })
    .where(and(inOrg(callingProxies), eq(callingProxies.id, id)))
    .returning();
  return proxyView(row ?? current);
}

export async function deleteProxy(id: string): Promise<void> {
  const view = await proxyView(await requireProxy(id));
  if (view.stationId) throw new CallApiError(409, `${view.stationName} uses this IP — give it another first`);
  await db.delete(callingProxies).where(and(inOrg(callingProxies), eq(callingProxies.id, id)));
}

/** The proxy as the call worker needs it: server URL and the decrypted password. */
export function workerProxy(row: ProxyRow): WorkerProxy {
  return {
    server: `${row.protocol}://${row.host}:${row.port}`,
    username: row.username,
    password: row.passwordEncrypted ? decryptCredentialText(row.passwordEncrypted) : null,
    timezone: row.timezone,
  };
}
