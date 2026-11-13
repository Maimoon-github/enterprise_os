/**
 * The shapes of GET /api/calling/overview, shared by the route, the query
 * (overview.ts) and the Overview page. Client-safe: types and pure helpers
 * only, no runtime imports.
 */

import type { ContactCallStatus } from "./contract";

/** The longest range the endpoint will answer, in days. */
export const MAX_OVERVIEW_RANGE_DAYS = 180;

export type CallingOverviewTotals = {
  /** Calls placed (rows created) in the range. */
  callsPlaced: number;
  /** Calls the lead picked up. */
  connected: number;
  /** connected / callsPlaced, 0..1; null when nothing was placed. */
  connectRate: number | null;
  /** Rang, nobody picked up (status no_recording). */
  didNotPickUp: number;
  notOnWhatsApp: number;
  /** Failed for any other reason (extension or WhatsApp error). */
  failed: number;
  /** Calls still pending or in progress. */
  inProgress: number;
  /** Sum of duration_ms over connected calls. */
  talkTimeMs: number;
  /** talkTimeMs / connected; null when nothing connected. */
  avgTalkTimeMs: number | null;
  /** Follow-up WhatsApp messages opened. */
  messagesSent: number;
  uniqueLeadsCalled: number;
};

export type CallingOverviewDay = {
  /** YYYY-MM-DD in the requested time zone. */
  date: string;
  calls: number;
  connected: number;
  didNotPickUp: number;
  messages: number;
};

/** The pipeline as it is now — not bound to the date range. */
export type CallingOverviewPipeline = {
  /** Not done, and follow-up due by the end of today (or to-call with no date). */
  dueToday: number;
  followUp: number;
  done: number;
  total: number;
  byCallStatus: Record<ContactCallStatus, number>;
};

export type CallingOverviewCampaignRow = {
  id: string;
  name: string;
  leads: number;
  calls: number;
  connected: number;
  connectRate: number | null;
  dueToday: number;
};

export type CallingOverviewResponse = {
  from: string;
  to: string;
  timeZone: string;
  campaignId: string | null;
  totals: CallingOverviewTotals;
  days: CallingOverviewDay[];
  pipeline: CallingOverviewPipeline;
  campaigns: CallingOverviewCampaignRow[];
};

export type CallingOverviewQuery = {
  /** YYYY-MM-DD, inclusive. */
  from: string;
  /** YYYY-MM-DD, inclusive. */
  to: string;
  campaignId?: string | null;
  /** IANA zone the days are bucketed in. */
  timeZone?: string | null;
};

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** True for a real calendar date written YYYY-MM-DD. */
export function isDateString(value: string): boolean {
  const match = DATE_RE.exec(value);
  if (!match) return false;
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

/** Every date from `from` to `to` inclusive, as YYYY-MM-DD; empty if either is invalid or from > to. */
export function listDays(from: string, to: string): string[] {
  if (!isDateString(from) || !isDateString(to) || from > to) return [];
  const out: string[] = [];
  const end = Date.parse(`${to}T00:00:00Z`);
  for (let t = Date.parse(`${from}T00:00:00Z`); t <= end; t += 86_400_000) {
    out.push(new Date(t).toISOString().slice(0, 10));
  }
  return out;
}

/** a / b as a 0..1 fraction; null when b is 0. */
export function rate(numerator: number, denominator: number): number | null {
  return denominator > 0 ? numerator / denominator : null;
}

/** Whole-number average, rounded; null when there is nothing to average. */
export function average(total: number, count: number): number | null {
  return count > 0 ? Math.round(total / count) : null;
}
