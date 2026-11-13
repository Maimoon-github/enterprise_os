import "server-only";

import { resolveTimeZone } from "@/lib/timeZone";
import { sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import { CONTACT_CALL_STATUSES, type CallStatus, type ContactCallStatus } from "./contract";
import { contactCallStatusForCall } from "./contactCallStatus";
import {
  average,
  listDays,
  rate,
  type CallingOverviewCampaignRow,
  type CallingOverviewDay,
  type CallingOverviewPipeline,
  type CallingOverviewQuery,
  type CallingOverviewResponse,
  type CallingOverviewTotals,
} from "./overviewContract";

export { resolveTimeZone };

/** One outcome bucket of a finished call, for the overview. */
export type CallOutcome = "connected" | "didNotPickUp" | "notOnWhatsApp" | "failed" | "inProgress";

/**
 * The overview's outcome for a call — derived from the lead's call status
 * (contactCallStatusForCall) so the classification lives in one place.
 */
export function outcomeForCall(call: { status: CallStatus; error: string | null }): CallOutcome {
  switch (contactCallStatusForCall(call)) {
    case "connected":
      return "connected";
    case "no_answer":
      return "didNotPickUp";
    case "not_on_whatsapp":
      return "notOnWhatsApp";
    case "calling":
      return "inProgress";
    default:
      return "failed";
  }
}

type CallGroup = {
  day?: string;
  campaign_id?: string;
  status: CallStatus;
  error: string | null;
  calls: number;
  talk_ms: number;
};

type Counts = Record<CallOutcome, number> & { calls: number; talkMs: number };

const emptyCounts = (): Counts => ({
  calls: 0,
  connected: 0,
  didNotPickUp: 0,
  notOnWhatsApp: 0,
  failed: 0,
  inProgress: 0,
  talkMs: 0,
});

function addGroup(counts: Counts, group: CallGroup) {
  const outcome = outcomeForCall(group);
  counts.calls += group.calls;
  counts[outcome] += group.calls;
  if (outcome === "connected") counts.talkMs += group.talk_ms;
}

/**
 * Buckets the grouped (day, status, error) rows into the response's totals and
 * per-day series. Pure, so the classification is testable without a database.
 */
export function summarizeCalls(
  groups: CallGroup[],
  days: string[],
  messagesByDay: Map<string, number>,
  uniqueLeadsCalled: number,
): { totals: CallingOverviewTotals; days: CallingOverviewDay[] } {
  const total = emptyCounts();
  const perDay = new Map<string, Counts>();
  for (const group of groups) {
    addGroup(total, group);
    if (group.day) {
      const counts = perDay.get(group.day) ?? emptyCounts();
      addGroup(counts, group);
      perDay.set(group.day, counts);
    }
  }
  const messagesSent = [...messagesByDay.values()].reduce((sum, n) => sum + n, 0);
  return {
    totals: {
      callsPlaced: total.calls,
      connected: total.connected,
      connectRate: rate(total.connected, total.calls),
      didNotPickUp: total.didNotPickUp,
      notOnWhatsApp: total.notOnWhatsApp,
      failed: total.failed,
      inProgress: total.inProgress,
      talkTimeMs: total.talkMs,
      avgTalkTimeMs: average(total.talkMs, total.connected),
      messagesSent,
      uniqueLeadsCalled,
    },
    days: days.map((date) => {
      const counts = perDay.get(date) ?? emptyCounts();
      return {
        date,
        calls: counts.calls,
        connected: counts.connected,
        didNotPickUp: counts.didNotPickUp,
        messages: messagesByDay.get(date) ?? 0,
      };
    }),
  };
}

/** A contact is due when it is not done and its date has come (or it was never given one). */
const DUE_SQL = (endOfToday: ReturnType<typeof sql>) =>
  sql`(ccc.stage <> 'done' AND ((ccc.follow_up_at IS NOT NULL AND ccc.follow_up_at < ${endOfToday}) OR (ccc.stage = 'to_call' AND ccc.follow_up_at IS NULL)))`;

export async function getCallingOverview(query: CallingOverviewQuery): Promise<CallingOverviewResponse> {
  const timeZone = resolveTimeZone(query.timeZone);
  const orgId = currentOrganizationId();
  const campaignId = query.campaignId ?? null;
  const dayList = listDays(query.from, query.to);

  // [from, to+1) in the caller's zone, as instants.
  const rangeStart = sql`(${query.from}::date)::timestamp AT TIME ZONE ${timeZone}`;
  const rangeEnd = sql`((${query.to}::date + 1)::timestamp) AT TIME ZONE ${timeZone}`;
  const endOfToday = sql`((date_trunc('day', now() AT TIME ZONE ${timeZone}) + interval '1 day') AT TIME ZONE ${timeZone})`;
  const dayOf = (column: ReturnType<typeof sql>) => sql`to_char((${column} AT TIME ZONE ${timeZone})::date, 'YYYY-MM-DD')`;
  const campaignJoin = campaignId
    ? (alias: string) => sql`JOIN call_campaign_contacts ${sql.raw(alias)} ON ${sql.raw(alias)}.id = t.campaign_contact_id AND ${sql.raw(alias)}.campaign_id = ${campaignId}::uuid`
    : () => sql``;

  const [callRows, leadRows, messageRows, pipelineRows, statusRows, campaignRows, campaignCallRows] = await Promise.all([
    db.execute<CallGroup & { day: string }>(sql`
      SELECT ${dayOf(sql`t.created_at`)} AS day, t.status, t.error,
             count(*)::int AS calls,
             coalesce(sum(t.duration_ms), 0)::float8 AS talk_ms
      FROM call_sessions t ${campaignJoin("c")}
      WHERE t.organization_id = ${orgId}::uuid AND t.created_at >= ${rangeStart} AND t.created_at < ${rangeEnd}
      GROUP BY 1, t.status, t.error`),
    db.execute<{ leads: number }>(sql`
      SELECT count(DISTINCT t.person_id)::int AS leads
      FROM call_sessions t ${campaignJoin("c")}
      WHERE t.organization_id = ${orgId}::uuid AND t.created_at >= ${rangeStart} AND t.created_at < ${rangeEnd}`),
    db.execute<{ day: string; messages: number }>(sql`
      SELECT ${dayOf(sql`t.opened_at`)} AS day, count(*)::int AS messages
      FROM call_messages t ${campaignJoin("c")}
      WHERE t.organization_id = ${orgId}::uuid AND t.opened_at >= ${rangeStart} AND t.opened_at < ${rangeEnd}
      GROUP BY 1`),
    db.execute<{ due: number; follow_up: number; done: number; total: number }>(sql`
      SELECT count(*) FILTER (WHERE ${DUE_SQL(endOfToday)})::int AS due,
             count(*) FILTER (WHERE ccc.stage = 'follow_up')::int AS follow_up,
             count(*) FILTER (WHERE ccc.stage = 'done')::int AS done,
             count(*)::int AS total
      FROM call_campaign_contacts ccc
      JOIN call_campaigns cc ON cc.id = ccc.campaign_id
      WHERE cc.organization_id = ${orgId}::uuid AND cc.archived_at IS NULL ${campaignId ? sql`AND cc.id = ${campaignId}::uuid` : sql``}`),
    db.execute<{ call_status: ContactCallStatus; n: number }>(sql`
      SELECT ccc.call_status, count(*)::int AS n
      FROM call_campaign_contacts ccc
      JOIN call_campaigns cc ON cc.id = ccc.campaign_id
      WHERE cc.organization_id = ${orgId}::uuid AND cc.archived_at IS NULL ${campaignId ? sql`AND cc.id = ${campaignId}::uuid` : sql``}
      GROUP BY 1`),
    db.execute<{ id: string; name: string; leads: number; due: number }>(sql`
      SELECT cc.id, cc.name, count(ccc.id)::int AS leads,
             count(ccc.id) FILTER (WHERE ${DUE_SQL(endOfToday)})::int AS due
      FROM call_campaigns cc
      LEFT JOIN call_campaign_contacts ccc ON ccc.campaign_id = cc.id
      WHERE cc.organization_id = ${orgId}::uuid AND cc.archived_at IS NULL
      GROUP BY cc.id, cc.name
      ORDER BY cc.created_at DESC`),
    db.execute<CallGroup & { campaign_id: string }>(sql`
      SELECT ccc.campaign_id, t.status, t.error,
             count(*)::int AS calls,
             coalesce(sum(t.duration_ms), 0)::float8 AS talk_ms
      FROM call_sessions t
      JOIN call_campaign_contacts ccc ON ccc.id = t.campaign_contact_id
      WHERE t.organization_id = ${orgId}::uuid AND t.created_at >= ${rangeStart} AND t.created_at < ${rangeEnd}
      GROUP BY 1, t.status, t.error`),
  ]);

  const messagesByDay = new Map(messageRows.map((row) => [row.day, row.messages]));
  const { totals, days } = summarizeCalls([...callRows], dayList, messagesByDay, leadRows[0]?.leads ?? 0);

  const pipelineRow = pipelineRows[0];
  const byCallStatus = Object.fromEntries(CONTACT_CALL_STATUSES.map((s) => [s, 0])) as Record<ContactCallStatus, number>;
  for (const row of statusRows) byCallStatus[row.call_status] = row.n;
  const pipeline: CallingOverviewPipeline = {
    dueToday: pipelineRow?.due ?? 0,
    followUp: pipelineRow?.follow_up ?? 0,
    done: pipelineRow?.done ?? 0,
    total: pipelineRow?.total ?? 0,
    byCallStatus,
  };

  const callsByCampaign = new Map<string, Counts>();
  for (const group of campaignCallRows) {
    const counts = callsByCampaign.get(group.campaign_id) ?? emptyCounts();
    addGroup(counts, group);
    callsByCampaign.set(group.campaign_id, counts);
  }
  const campaigns: CallingOverviewCampaignRow[] = campaignRows.map((row) => {
    const counts = callsByCampaign.get(row.id) ?? emptyCounts();
    return {
      id: row.id,
      name: row.name,
      leads: row.leads,
      calls: counts.calls,
      connected: counts.connected,
      connectRate: rate(counts.connected, counts.calls),
      dueToday: row.due,
    };
  });

  return { from: query.from, to: query.to, timeZone, campaignId, totals, days, pipeline, campaigns };
}
