/**
 * Stage 1 — Liveness. A brand qualifies as "live" if its Shopify storefront is
 * reachable and not a closed / 404 / "store unavailable" page. Cheapest check,
 * so it runs first.
 */

const DEAD_STORE_PATTERNS = [
  /this store is unavailable/i,
  /sorry, this shop is currently unavailable/i,
  /this shop is currently unavailable/i,
  /store unavailable/i,
  /shop unavailable/i,
];

const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  Accept:
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
  "Cache-Control": "no-cache",
};

export interface LivenessResult {
  isLive: boolean;
  reason?: string;
}

function buildCandidateUrls(domain: string): string[] {
  const cleanDomain = domain.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  const hostVariants = cleanDomain.startsWith("www.")
    ? [cleanDomain, cleanDomain.replace(/^www\./, "")]
    : [cleanDomain, `www.${cleanDomain}`];

  return [...new Set(hostVariants.flatMap((host) => [`https://${host}`, `http://${host}`]))];
}

export async function checkLiveness(domain: string): Promise<LivenessResult> {
  let lastReason = "unreachable";

  for (const url of buildCandidateUrls(domain)) {
    try {
      const res = await fetch(url, {
        redirect: "follow",
        headers: BROWSER_HEADERS,
        // Storefronts can be slow; cap the wait.
        signal: AbortSignal.timeout(15_000),
      });

      const body = await res.text();
      for (const pattern of DEAD_STORE_PATTERNS) {
        if (pattern.test(body)) {
          return { isLive: false, reason: "Shopify store unavailable" };
        }
      }

      if (res.status === 404 || res.status === 410) {
        lastReason = `HTTP ${res.status}`;
        continue;
      }

      // A password-protected store still exists (not "closed"), so we treat it as
      // live but record the note for downstream visibility.
      if (res.url.includes("/password")) {
        return { isLive: true, reason: "password protected" };
      }

      if (res.status >= 400) {
        return { isLive: true, reason: `reachable but returned HTTP ${res.status}` };
      }

      return { isLive: true };
    } catch (err) {
      lastReason = err instanceof Error ? err.message : "unreachable";
    }
  }

  return { isLive: false, reason: `unreachable: ${lastReason}` };
}
