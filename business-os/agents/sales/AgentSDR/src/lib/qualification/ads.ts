/**
 * Stage 2 — Ads. Is the brand actively advertising? Only brands running ads are
 * worth outreach. The real provider (SerpApi / BigSpy / other) is still TBD, so
 * this is a pluggable adapter: pick the provider via the ADS_PROVIDER env var.
 */
import { env } from "./config";

export interface AdsCheckInput {
  domain: string;
  brandName?: string | null;
}

export interface AdsCheckResult {
  isRunningAds: boolean;
  activeAdCount: number;
  /** Provider-specific note (error, fallback, etc.). */
  note?: string;
}

export interface AdsProvider {
  name: string;
  checkAds(input: AdsCheckInput): Promise<AdsCheckResult>;
}

/** Offline/dev provider: deterministic so tests are reproducible. */
const mockAdsProvider: AdsProvider = {
  name: "mock",
  async checkAds({ domain }) {
    // Deterministic pseudo-result based on the domain string, so the same
    // domain always returns the same answer during development.
    const hash = [...domain].reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    const count = hash % 5; // 0..4
    return {
      isRunningAds: count > 0,
      activeAdCount: count,
      note: "mock provider — wire a real ads API before production",
    };
  },
};

/**
 * Skeleton for a real HTTP-based ads provider. Fill in the request/response
 * mapping once the provider is chosen; the rest of the pipeline is unaffected.
 */
function httpAdsProvider(name: string): AdsProvider {
  return {
    name,
    async checkAds({ domain, brandName }) {
      if (!env.adsApiKey || !env.adsBaseUrl) {
        throw new Error(
          `Ads provider "${name}" is not configured (set ADS_API_KEY and ADS_BASE_URL).`,
        );
      }
      const params = new URLSearchParams({
        api_key: env.adsApiKey,
        query: brandName || domain,
        domain,
      });
      const res = await fetch(`${env.adsBaseUrl}?${params.toString()}`, {
        signal: AbortSignal.timeout(20_000),
      });
      if (!res.ok) {
        throw new Error(`Ads provider "${name}" returned HTTP ${res.status}`);
      }
      const data = (await res.json()) as { ads?: unknown[] };
      const activeAdCount = Array.isArray(data.ads) ? data.ads.length : 0;
      return { isRunningAds: activeAdCount > 0, activeAdCount };
    },
  };
}

export function getAdsProvider(): AdsProvider {
  switch (env.adsProvider) {
    case "mock":
      return mockAdsProvider;
    default:
      return httpAdsProvider(env.adsProvider);
  }
}

export function checkAds(input: AdsCheckInput): Promise<AdsCheckResult> {
  return getAdsProvider().checkAds(input);
}
