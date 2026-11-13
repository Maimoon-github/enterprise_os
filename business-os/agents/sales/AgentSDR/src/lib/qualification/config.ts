/**
 * Central configuration for the brand qualification pipeline.
 */

export const QUALIFICATION_CONFIG = {
  /** Minimum verified-email people (Apollo total_entries) for "Apollo has data". */
  minVerifiedEmployees: 10,
  /** Default campaign lead target if none supplied. */
  defaultLeadTarget: 3000,
  /** Re-check window for soft-fail statuses (not_live). 30 days. */
  recheckTtlMs: 1000 * 60 * 60 * 24 * 30,
  /**
   * Min ms between Apollo api_search calls. The endpoint allows ~600/hr
   * (~1 per 6s) on most plans. Default 0 for dev; set APOLLO_THROTTLE_MS to
   * ~6000 in production to stay under the limit.
   */
  apolloThrottleMs: Number(process.env.APOLLO_THROTTLE_MS ?? 0),
} as const;

/** Statuses that are never re-checked once set. */
export const STICKY_STATUSES = new Set(["qualified", "apollo_no_data"]);

export const env = {
  /** Must be a MASTER key for mixed_people/api_search (else 403). */
  apolloApiKey: process.env.APOLLO_API_KEY ?? "",
  apolloBaseUrl: process.env.APOLLO_BASE_URL ?? "https://api.apollo.io/api/v1",
  // Ads is deferred; kept for when the stage is re-enabled.
  adsProvider: process.env.ADS_PROVIDER ?? "mock",
  adsApiKey: process.env.ADS_API_KEY ?? "",
  adsBaseUrl: process.env.ADS_BASE_URL ?? "",
};
