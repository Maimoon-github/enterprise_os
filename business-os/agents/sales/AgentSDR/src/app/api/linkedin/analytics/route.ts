import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, eq, gte, isNotNull, lte, ne, type SQL } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { leads, messages as messagesTable, type MessageType } from "@/lib/linkedin/schema";
import { DEFAULT_WORK_TIMEZONE } from "@/lib/linkedin/workingHours";
import {
  addCalendarDays,
  calendarDayBoundsInZone,
  eachCalendarDay,
  formatHourBucketLabel,
  formatZonedDayLabel,
  getZonedHour,
} from "@/lib/linkedin/timezone";

type ActivitySlot = {
  connectionsSent: number;
  connectionsAccepted: number;
  messagesSent: number;
  messageReplies: number;
};

const emptySlot = (): ActivitySlot => ({
  connectionsSent: 0,
  connectionsAccepted: 0,
  messagesSent: 0,
  messageReplies: 0,
});

const applyOutboundMessage = (slot: ActivitySlot, type: MessageType) => {
  if (type === "INVITATION") {
    slot.connectionsSent++;
  } else if (type === "ACCEPTANCE") {
    slot.connectionsAccepted++;
    slot.messagesSent++;
  } else if (
    type === "FOLLOW_UP_1" ||
    type === "FOLLOW_UP_2" ||
    type === "FOLLOW_UP_3" ||
    type === "CUSTOM_SENT"
  ) {
    slot.messagesSent++;
  }
};

const tallyOutboundTotals = (messages: { type: MessageType }[]) => {
  let connectionsSent = 0;
  let connectionsAccepted = 0;
  let messagesSent = 0;

  for (const m of messages) {
    if (m.type === "INVITATION") connectionsSent++;
    else if (m.type === "ACCEPTANCE") {
      connectionsAccepted++;
      messagesSent++;
    } else if (
      m.type === "FOLLOW_UP_1" ||
      m.type === "FOLLOW_UP_2" ||
      m.type === "FOLLOW_UP_3" ||
      m.type === "CUSTOM_SENT"
    ) {
      messagesSent++;
    }
  }

  return { connectionsSent, connectionsAccepted, messagesSent };
};

export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const { searchParams } = req.nextUrl;
    const accountId = searchParams.get("accountId") || null;
    const campaignId = searchParams.get("campaignId") || null;
    const startDateStr = searchParams.get("startDate");
    const endDateStr = searchParams.get("endDate");
    const timeZone = searchParams.get("timezone")?.trim() || DEFAULT_WORK_TIMEZONE;

    const defaultEndStr = new Date().toLocaleDateString("en-CA", { timeZone });
    const defaultStartStr = addCalendarDays(defaultEndStr, -29);

    const rangeStartStr = startDateStr || defaultStartStr;
    const rangeEndStr = endDateStr || defaultEndStr;

    const startDate = calendarDayBoundsInZone(rangeStartStr, timeZone).start;
    const endDate = calendarDayBoundsInZone(rangeEndStr, timeZone).end;

    // Prisma expressed this as a `lead: { ... }` relation filter, which only
    // matches messages that actually have a Lead — an inner join here.
    const leadFilter: SQL[] = [
      ...(accountId ? [eq(leads.linkedinAccountId, accountId)] : []),
      ...(campaignId ? [eq(leads.campaignId, campaignId)] : []),
    ];
    const hasLeadFilter = leadFilter.length > 0;

    const outboundWhere = and(
      inOrg(messagesTable),
      gte(messagesTable.createdAt, startDate),
      lte(messagesTable.createdAt, endDate),
      ne(messagesTable.type, "RECEIVED"),
      ...leadFilter
    );

    const messages = hasLeadFilter
      ? await db
          .select({ type: messagesTable.type, createdAt: messagesTable.createdAt })
          .from(messagesTable)
          .innerJoin(leads, eq(messagesTable.leadId, leads.id))
          .where(outboundWhere)
      : await db
          .select({ type: messagesTable.type, createdAt: messagesTable.createdAt })
          .from(messagesTable)
          .where(outboundWhere);

    const repliesWhere = and(
      inOrg(messagesTable),
      eq(messagesTable.type, "RECEIVED"),
      isNotNull(messagesTable.leadId),
      gte(messagesTable.createdAt, startDate),
      lte(messagesTable.createdAt, endDate),
      ...leadFilter
    );

    const leadReplies = hasLeadFilter
      ? await db
          .select({ leadId: messagesTable.leadId, createdAt: messagesTable.createdAt })
          .from(messagesTable)
          .innerJoin(leads, eq(messagesTable.leadId, leads.id))
          .where(repliesWhere)
      : await db
          .select({ leadId: messagesTable.leadId, createdAt: messagesTable.createdAt })
          .from(messagesTable)
          .where(repliesWhere);

    const totals = tallyOutboundTotals(messages);
    const repliedLeadIds = new Set<string>();

    const useHourly = rangeStartStr === rangeEndStr;
    const bucketKeys: string[] = [];
    const byBucket: Record<string, ActivitySlot> = {};
    const repliesByBucket: Record<string, Set<string>> = {};

    if (useHourly) {
      for (let h = 0; h < 24; h++) {
        const label = formatHourBucketLabel(h);
        bucketKeys.push(label);
        byBucket[label] = emptySlot();
        repliesByBucket[label] = new Set();
      }
    } else {
      for (const dayStr of eachCalendarDay(rangeStartStr, rangeEndStr)) {
        const label = formatZonedDayLabel(
          calendarDayBoundsInZone(dayStr, timeZone).start,
          timeZone
        );
        bucketKeys.push(label);
        byBucket[label] = emptySlot();
        repliesByBucket[label] = new Set();
      }
    }

    const bucketFor = (createdAt: Date) =>
      useHourly
        ? formatHourBucketLabel(getZonedHour(createdAt, timeZone))
        : formatZonedDayLabel(createdAt, timeZone);

    for (const m of messages) {
      const label = bucketFor(new Date(m.createdAt));
      const slot = byBucket[label];
      if (!slot) continue;
      applyOutboundMessage(slot, m.type);
    }

    for (const m of leadReplies) {
      const leadId = m.leadId!;
      repliedLeadIds.add(leadId);
      const label = bucketFor(new Date(m.createdAt));
      repliesByBucket[label]?.add(leadId);
    }

    for (const key of bucketKeys) {
      byBucket[key].messageReplies = repliesByBucket[key]?.size ?? 0;
    }

    const chartData = bucketKeys.map((date) => ({ date, ...byBucket[date] }));

    return NextResponse.json({
      ok: true,
      granularity: useHourly ? "hour" : "day",
      stats: {
        ...totals,
        messageReplies: repliedLeadIds.size,
      },
      chartData,
    });
  });
}
