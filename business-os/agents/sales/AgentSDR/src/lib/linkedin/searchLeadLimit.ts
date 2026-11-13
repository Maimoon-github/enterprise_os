/**
 * Pure quota arithmetic — no database access, so client components can import
 * this. The one DB-backed helper lives in ./searchLeadLimit.server, because a
 * module-level `db` import here pulls the postgres driver into the browser
 * bundle and fails the build.
 */

import { defaultValues } from "@/lib/channels/rules";

/**
 * Leads one account may pull from searches a day when the organization has
 * not changed it (Settings → LinkedIn → Sending rules: searchLeadsPerDay).
 * Server code passes the organization's value as `limit`.
 */
export const DAILY_SEARCH_LEAD_LIMIT = defaultValues("linkedin").searchLeadsPerDay;

export type SearchUsage = {
  used: number;
  limit: number;
  remaining: number;
  limitReached: boolean;
};

export type SearchRemainingTier = "green" | "yellow" | "red";

/** Green above half the daily limit left, red below an eighth (200 / 50 of the default 400). */
export const getSearchRemainingTier = (remaining: number, limit: number = DAILY_SEARCH_LEAD_LIMIT): SearchRemainingTier => {
  if (remaining > limit / 2) return "green";
  if (remaining < limit / 8) return "red";
  return "yellow";
};

export const getSearchUsage = (used: number, limit: number = DAILY_SEARCH_LEAD_LIMIT): SearchUsage => ({
  used,
  limit,
  remaining: Math.max(0, limit - used),
  limitReached: used >= limit,
});

export const searchLimitErrorMessage = (usage: SearchUsage): string =>
  `This account has reached its daily search limit (${usage.used}/${usage.limit} leads). It resets with the daily limits job.`;

export const assertSearchQuotaAvailable = (searchLeadsToday: number, limit: number = DAILY_SEARCH_LEAD_LIMIT): void => {
  const usage = getSearchUsage(searchLeadsToday, limit);
  if (usage.limitReached) {
    throw new Error(searchLimitErrorMessage(usage));
  }
};
