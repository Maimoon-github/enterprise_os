/**
 * Apollo People API Search client.
 *
 * Uses POST /mixed_people/api_search — the API-optimized search that does NOT
 * consume credits (the older /mixed_people/search is deprecated for API callers
 * and returns 422). Requires a MASTER api key in the x-api-key header (else 403).
 * It returns no actual emails, only counts and boolean flags, which is all we
 * need: `total_entries` is the qualification signal.
 *
 * Validated against the live API: apollo.io + contact_email_status=verified ->
 * total_entries 635; a non-existent domain -> 0.
 */
import { env, QUALIFICATION_CONFIG } from "./config";
import type { ApolloLeadDebugTrace, ApolloSearchDebugTrace } from "./types";

let lastCallAt = 0;

/** Throttle to respect Apollo's ~600 req/hr limit on api_search. */
async function throttle(): Promise<void> {
  const minGap = QUALIFICATION_CONFIG.apolloThrottleMs;
  if (minGap <= 0) return;
  const wait = lastCallAt + minGap - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastCallAt = Date.now();
}

function requireKey(): string {
  if (!env.apolloApiKey) throw new Error("APOLLO_API_KEY is not set (needs a master key)");
  return env.apolloApiKey;
}

function paramsToRecord(params: URLSearchParams): Record<string, string | string[]> {
  const record: Record<string, string | string[]> = {};
  for (const [key, value] of params.entries()) {
    const existing = record[key];
    if (Array.isArray(existing)) existing.push(value);
    else if (existing !== undefined) record[key] = [existing, value];
    else record[key] = value;
  }
  return record;
}

async function apolloSearchWithDebug(
  label: ApolloSearchDebugTrace["label"],
  params: URLSearchParams,
): Promise<{ count: number; debug: ApolloSearchDebugTrace }> {
  await throttle();
  const url = `${env.apolloBaseUrl}/mixed_people/api_search?${params.toString()}`;
  const startedAt = new Date().toISOString();
  const baseDebug = {
    label,
    method: "POST" as const,
    url,
    query: paramsToRecord(params),
    totalEntries: null,
    startedAt,
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      accept: "application/json",
      "x-api-key": requireKey(),
    },
    signal: AbortSignal.timeout(30_000),
  });
  let data: unknown = null;
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw Object.assign(new Error(`Apollo api_search -> HTTP ${res.status}: ${text.slice(0, 300)}`), {
      debug: {
        ...baseDebug,
        status: res.status,
        response: text,
        error: text.slice(0, 1000),
        finishedAt: new Date().toISOString(),
      } satisfies ApolloSearchDebugTrace,
    });
  }
  data = await res.json();
  const totalEntries = (data as { total_entries?: number }).total_entries ?? 0;
  return {
    count: totalEntries,
    debug: {
      ...baseDebug,
      status: res.status,
      response: data,
      totalEntries,
      finishedAt: new Date().toISOString(),
    },
  };
}

function normalizeDomains(domains: string | string[]) {
  return [...new Set((Array.isArray(domains) ? domains : [domains]).map((domain) => domain.trim().toLowerCase()).filter(Boolean))];
}

function appendDomainParams(params: URLSearchParams, domains: string[]) {
  for (const domain of domains) {
    params.append("q_organization_domains_list[]", domain);
  }
}

/** Count ALL people Apollo has for one or more domains (no email filter). */
export async function countAllPeople(domain: string | string[]): Promise<number> {
  const domains = normalizeDomains(domain);
  const params = new URLSearchParams();
  appendDomainParams(params, domains);
  params.set("per_page", "1");
  const { count } = await apolloSearchWithDebug("all_people", params);
  return count;
}

/**
 * Count verified-email people Apollo has for a domain. Reads `total_entries`
 * from a single request (per_page=1), so the result is exact and cheap.
 */
export async function countVerifiedPeople(domain: string | string[]): Promise<number> {
  const domains = normalizeDomains(domain);
  const params = new URLSearchParams();
  appendDomainParams(params, domains);
  params.append("contact_email_status[]", "verified");
  params.set("per_page", "1");
  const { count } = await apolloSearchWithDebug("verified_people", params);
  return count;
}

/** Fetch both all and verified counts for a domain in sequence. */
export async function countLeads(
  domain: string | string[],
): Promise<{ allLeads: number; verifiedLeads: number }> {
  const { allLeads, verifiedLeads } = await countLeadsWithDebug(domain);
  return { allLeads, verifiedLeads };
}

export async function countLeadsWithDebug(
  domain: string | string[],
): Promise<{ allLeads: number; verifiedLeads: number; debug: ApolloLeadDebugTrace }> {
  const domains = normalizeDomains(domain);
  const primaryDomain = domains[0] ?? "";
  const allParams = new URLSearchParams();
  appendDomainParams(allParams, domains);
  allParams.set("per_page", "1");

  const verifiedParams = new URLSearchParams();
  appendDomainParams(verifiedParams, domains);
  verifiedParams.append("contact_email_status[]", "verified");
  verifiedParams.set("per_page", "1");

  let allResult: Awaited<ReturnType<typeof apolloSearchWithDebug>> | null = null;
  let verifiedResult: Awaited<ReturnType<typeof apolloSearchWithDebug>> | null = null;

  try {
    allResult = await apolloSearchWithDebug("all_people", allParams);
    verifiedResult = await apolloSearchWithDebug("verified_people", verifiedParams);
  } catch (error) {
    const debug = (error as { debug?: ApolloSearchDebugTrace }).debug;
    if (debug) {
      throw Object.assign(error instanceof Error ? error : new Error(String(error)), {
        debug: {
          domain: primaryDomain,
          domains,
          allPeople:
            allResult?.debug ??
            (debug.label === "all_people"
              ? debug
              : {
                  label: "all_people" as const,
                  method: "POST" as const,
                  url: `${env.apolloBaseUrl}/mixed_people/api_search?${allParams.toString()}`,
                  query: paramsToRecord(allParams),
                  totalEntries: null,
                  startedAt: new Date().toISOString(),
                  finishedAt: new Date().toISOString(),
                }),
          verifiedPeople:
            verifiedResult?.debug ??
            (debug.label === "verified_people"
              ? debug
              : {
                  label: "verified_people" as const,
                  method: "POST" as const,
                  url: `${env.apolloBaseUrl}/mixed_people/api_search?${verifiedParams.toString()}`,
                  query: paramsToRecord(verifiedParams),
                  totalEntries: null,
                  startedAt: new Date().toISOString(),
                  finishedAt: new Date().toISOString(),
                }),
        } satisfies ApolloLeadDebugTrace,
      });
    }
    throw error;
  }

  return {
    allLeads: allResult.count,
    verifiedLeads: verifiedResult.count,
    debug: {
      domain: primaryDomain,
      domains,
      allPeople: allResult.debug,
      verifiedPeople: verifiedResult.debug,
    },
  };
}
