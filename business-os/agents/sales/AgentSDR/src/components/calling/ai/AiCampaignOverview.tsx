"use client";

import {
  RiCalendarCheckLine,
  RiChat1Line,
  RiCheckboxCircleLine,
  RiCustomerService2Line,
  RiErrorWarningLine,
  RiHourglassLine,
  RiPhoneLine,
  RiPercentLine,
  RiStarLine,
  RiStopCircleLine,
  RiTeamLine,
  RiThumbDownLine,
} from "@remixicon/react";
import { BarList, type BarListItem } from "@/components/analytics/kit/BarList";
import { ChartCard } from "@/components/analytics/kit/ChartCard";
import { ChartLegend } from "@/components/analytics/kit/ChartLegend";
import { DonutChart, type DonutItem } from "@/components/analytics/kit/DonutChart";
import { Frame, FrameHeader, FramePanel } from "@/components/analytics/kit/Frame";
import { FunnelChart } from "@/components/analytics/kit/FunnelChart";
import { KpiCell, KpiStrip } from "@/components/analytics/kit/KpiStrip";
import { TimeSeriesChart, TimeSeriesTable, type SeriesKeys } from "@/components/analytics/kit/TimeSeriesChart";
import { CHANNEL_META, formatCompact, formatPercent, HUE, MUTED, STATUS } from "@/components/analytics/theme";
import { Skeleton } from "@/components/page/Skeletons";
import { AGENT_OUTCOME_LABELS, AGENT_OUTCOMES } from "@/lib/calls/contract";
import type { AiCampaignDetail, AiCampaignStats } from "@/lib/calls/aiCampaigns/api";

const WA = CHANNEL_META.whatsapp.color;
const DAY_KEYS: SeriesKeys<"answered" | "unanswered"> = {
  answered: { label: "Answered", color: WA },
  unanswered: { label: "Not answered", color: MUTED },
};
const OUTCOME_COLOR: Record<(typeof AGENT_OUTCOMES)[number], string> = {
  meeting_booked: HUE.green,
  interested: HUE.teal,
  human_callback: HUE.sky,
  call_back: HUE.blue,
  not_interested: HUE.red,
  wrong_person: HUE.orange,
  do_not_contact: HUE.red,
  no_response: MUTED,
  other: MUTED,
};

const pct = (part: number, whole: number): string | undefined => (whole > 0 ? formatPercent(part / whole) : undefined);

/** The Overview tab: headline numbers for the team, where leads stand, the per-step funnel, outcomes and calls per day. */
export function AiCampaignOverview({ campaign, stats }: { campaign: AiCampaignDetail; stats: AiCampaignStats | null }) {
  if (!stats) {
    return (
      <div aria-busy="true" aria-label="Loading" className="space-y-4">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }
  const s = stats;
  const inProgress = s.byStatus.queued + s.byStatus.reaching + s.byStatus.callback;
  const leadStates: DonutItem[] = [
    { key: "progress", label: "In progress", value: inProgress, color: HUE.amber, icon: RiHourglassLine },
    { key: "chasing", label: "Waiting for booking", value: s.byStatus.chasing, color: HUE.purple, icon: RiCalendarCheckLine },
    { key: "booked", label: "Meeting booked", value: s.byStatus.booked, color: STATUS.good, icon: RiCheckboxCircleLine },
    { key: "team", label: "For the team", value: s.byStatus.handoff + s.byStatus.replied, color: HUE.teal, icon: RiCustomerService2Line },
    { key: "no", label: "Not interested", value: s.byStatus.not_interested, color: MUTED, icon: RiThumbDownLine },
    { key: "ended", label: "Unreached, stopped or failed", value: s.byStatus.unreached + s.byStatus.stopped + s.byStatus.failed, color: STATUS.critical, icon: RiStopCircleLine },
  ];

  const reachSteps = s.perStep.filter((step) => step.phase === "reach");
  const chaseSteps = s.perStep.filter((step) => step.phase !== "reach");
  const outcomes: BarListItem[] = AGENT_OUTCOMES.filter((key) => (s.outcomes[key] ?? 0) > 0).map((key) => ({
    key,
    label: AGENT_OUTCOME_LABELS[key],
    value: s.outcomes[key] ?? 0,
    color: OUTCOME_COLOR[key],
  }));
  const series = {
    keys: ["answered", "unanswered"] as const,
    points: s.callsByDay.map((day) => ({ date: day.date, answered: day.answered, unanswered: Math.max(day.placed - day.answered, 0) })),
  };
  const limit = campaign.callsPerDayLimit;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
      <KpiStrip className="lg:col-span-12" columns={6}>
        <KpiCell icon={RiTeamLine} label="Leads" value={formatCompact(s.total)} context={s.byStatus.queued > 0 ? `${formatCompact(s.byStatus.queued)} not called yet` : s.total > 0 ? "Everyone has been reached out to" : undefined} />
        <KpiCell
          icon={RiPhoneLine}
          label="Calls today"
          value={`${formatCompact(s.callsToday)}${limit > 0 ? ` / ${formatCompact(limit)}` : ""}`}
          context={`${formatCompact(s.callsPlaced)} placed in all`}
          hint="Calls this campaign placed today, against the most its numbers may place a day (their own limit or the Sending rule; a number still warming up places fewer)."
        />
        <KpiCell icon={RiPercentLine} label="Answered" value={formatPercent(s.callsPlaced > 0 ? s.callsAnswered / s.callsPlaced : null)} context={s.callsPlaced > 0 ? `${s.callsAnswered.toLocaleString("en-US")} of ${s.callsPlaced.toLocaleString("en-US")} calls` : "No calls yet"} hint="Calls that were picked up and recorded." />
        <KpiCell icon={RiChat1Line} label="Conversations" value={formatCompact(s.conversations)} context={pct(s.conversations, s.callsPlaced) ? `${pct(s.conversations, s.callsPlaced)} of calls` : undefined} hint="Calls where the lead actually talked. Picking up and saying nothing does not count." />
        <KpiCell icon={RiStarLine} label="Interested" value={formatCompact(s.interested)} context={pct(s.interested, s.conversations) ? `${pct(s.interested, s.conversations)} of conversations` : undefined} hint="Leads whose call ended interested, meeting agreed, or wanting the team to call." />
        <KpiCell icon={RiCalendarCheckLine} label="Booked" value={formatCompact(s.booked)} context={s.handoffs > 0 ? `${formatCompact(s.handoffs)} handed to the team` : s.messagesSent > 0 ? `${formatCompact(s.messagesSent)} messages sent` : undefined} hint="Meetings Cal.com reported. Leads handed to the team are in Action required." />
      </KpiStrip>

      <Frame className="self-start lg:col-span-5">
        <FrameHeader title="Where leads stand" description="Every lead, by where it is now." />
        <FramePanel>
          <DonutChart items={leadStates} centerLabel="leads" emptyLabel="No leads yet" emptyDescription="Add leads to see where they stand." />
        </FramePanel>
      </Frame>

      <Frame className="lg:col-span-7">
        <FrameHeader title="Reach funnel" description="How many leads got to each step of the sequence." />
        <FramePanel>
          {reachSteps.some((step) => step.attempted > 0) ? (
            <FunnelChart stages={reachSteps.map((step) => ({ key: step.key, label: step.label, value: step.attempted }))} />
          ) : (
            <p className="py-6 text-center text-paragraph-sm text-text-sub-600">No steps have run yet.</p>
          )}
          {chaseSteps.some((step) => step.attempted > 0) && (
            <div className="mt-5 border-t border-stroke-soft-200 pt-4">
              <p className="mb-3 text-label-sm text-text-strong-950">After a yes, before booking</p>
              <BarList items={chaseSteps.filter((step) => step.attempted > 0).map((step) => ({ key: step.key, label: step.label, value: step.attempted, color: HUE.purple }))} />
            </div>
          )}
        </FramePanel>
      </Frame>

      <ChartCard
        className="lg:col-span-8"
        title="Calls per day"
        description="Calls placed each day for the last 14 days, answered or not."
        legend={<ChartLegend items={[{ label: "Answered", color: DAY_KEYS.answered.color }, { label: "Not answered", color: DAY_KEYS.unanswered.color }]} />}
        table={<TimeSeriesTable series={series} keys={DAY_KEYS} bucket="day" caption="Calls per day" />}
      >
        <TimeSeriesChart series={series} keys={DAY_KEYS} type="stackedBar" bucket="day" />
      </ChartCard>

      <Frame className="self-start lg:col-span-4">
        <FrameHeader title="What the agent heard" description="How each recorded conversation ended." />
        <FramePanel>
          <BarList items={outcomes} emptyLabel="No conversations yet." />
          {s.callsPlaced > s.callsAnswered && (
            <p className="mt-4 flex items-center gap-1.5 text-paragraph-xs text-text-sub-600">
              <RiErrorWarningLine className="size-3.5 shrink-0" aria-hidden="true" />
              {(s.callsPlaced - s.callsAnswered).toLocaleString("en-US")} calls were not answered or not recorded.
            </p>
          )}
        </FramePanel>
      </Frame>
    </div>
  );
}
