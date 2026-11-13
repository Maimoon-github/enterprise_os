"use client";

import { useState } from "react";
import {
  RiCheckboxCircleLine,
  RiErrorWarningLine,
  RiForbid2Line,
  RiLoader4Line,
  RiMailCheckLine,
  RiMailSendLine,
  RiReplyLine,
  RiTeamLine,
  RiTimeLine,
} from "@remixicon/react";

import * as SegmentedControl from "@/components/alignui/segmented-control";
import { ChartCard } from "@/components/analytics/kit/ChartCard";
import { DonutChart, type DonutItem } from "@/components/analytics/kit/DonutChart";
import { EmptyChart } from "@/components/analytics/kit/EmptyChart";
import { Frame, FrameHeader, FramePanel } from "@/components/analytics/kit/Frame";
import { FunnelChart } from "@/components/analytics/kit/FunnelChart";
import { KpiCell, KpiStrip } from "@/components/analytics/kit/KpiStrip";
import { SeriesStats } from "@/components/analytics/kit/SeriesStats";
import { seriesTotal, TimeSeriesChart, TimeSeriesTable, type SeriesKeys } from "@/components/analytics/kit/TimeSeriesChart";
import { CHANNEL_META, formatCompact, formatPercent, MUTED, STATUS } from "@/components/analytics/theme";
import type { DailySends } from "@/lib/outreach/campaigns";

type Stats = {
  totalLeads: number;
  pending: number;
  inSequence: number;
  replied: number;
  completed: number;
  bounced: number;
  suppressed: number;
  emailsSent: number;
  emailsScheduled: number;
  emailsFailed: number;
  emailsTotal: number;
  contacted: number;
};
type StepBreakdown = { stepNumber: number; sent: number }[];

/**
 * A send campaign's analytics, in the Analytics kit: headline numbers, where
 * every lead stands (a donut — the states are exclusive and sum to the
 * leads), daily send volume, and how many leads each step reached.
 *
 * Colour: sent wears the email channel colour, as on the Analytics Email
 * view; scheduled is the de-emphasis gray (it hasn't happened); failed is the
 * critical status colour, labelled. Lead states are ordered so adjacent
 * slices, and the ring's seam, pass the colour-blind check.
 */

const EMAIL = CHANNEL_META.email.color;

type SendKey = "sent" | "scheduled" | "failed";
const SEND_KEYS: SeriesKeys<SendKey> = {
  sent: { label: "Sent", color: EMAIL },
  scheduled: { label: "Scheduled", color: MUTED },
  failed: { label: "Failed", color: STATUS.critical },
};

const RANGES = [7, 14, 30] as const;
type Range = (typeof RANGES)[number];

function pct(part: number, whole: number, digits?: number): string | undefined {
  return whole > 0 ? formatPercent(part / whole, digits) : undefined;
}

export default function AnalyticsTab({ stats, stepBreakdown, dailySends }: { stats: Stats; stepBreakdown: StepBreakdown; dailySends: DailySends }) {
  const [range, setRange] = useState<Range>(14);
  const blocked = stats.bounced + stats.suppressed;
  const progress = stats.emailsTotal > 0 ? stats.emailsSent / stats.emailsTotal : 0;

  const series = { keys: ["sent", "scheduled", "failed"] as const, points: dailySends.slice(-range) };
  const sendStats = (Object.keys(SEND_KEYS) as SendKey[]).map((k) => ({ label: SEND_KEYS[k].label, color: SEND_KEYS[k].color, value: formatCompact(seriesTotal(series, k)) }));

  const leadStates: DonutItem[] = [
    { key: "inSequence", label: "In progress", value: stats.inSequence, color: "#e5930a", icon: RiLoader4Line },
    { key: "pending", label: "Yet to start", value: stats.pending, color: MUTED, icon: RiTimeLine },
    { key: "completed", label: "Completed", value: stats.completed, color: STATUS.good, icon: RiCheckboxCircleLine },
    { key: "replied", label: "Replied", value: stats.replied, color: "#7d52f4", icon: RiReplyLine },
    { key: "blocked", label: "Bounced or unsubscribed", value: blocked, color: STATUS.critical, icon: RiForbid2Line },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
      <KpiStrip className="lg:col-span-12" columns={6}>
        <KpiCell icon={RiTeamLine} label="Leads" value={formatCompact(stats.totalLeads)} context="In this campaign" />
        <KpiCell icon={RiMailCheckLine} label="Contacted" value={formatCompact(stats.contacted)} context={pct(stats.contacted, stats.totalLeads) ? `${pct(stats.contacted, stats.totalLeads)} of leads` : undefined} />
        <KpiCell icon={RiMailSendLine} label="Emails sent" value={formatCompact(stats.emailsSent)} context={stats.emailsScheduled > 0 ? `${stats.emailsScheduled.toLocaleString("en-US")} still scheduled` : "Nothing scheduled"} />
        <KpiCell icon={RiReplyLine} label="Replied" value={formatCompact(stats.replied)} context={pct(stats.replied, stats.contacted, 2) ? `${pct(stats.replied, stats.contacted, 2)} of contacted` : undefined} hint="Leads who replied to any step. Replies aren't attributed to a step." />
        <KpiCell icon={RiForbid2Line} label="Bounced" value={formatCompact(stats.bounced)} context={pct(stats.bounced, stats.contacted, 1) ? `${pct(stats.bounced, stats.contacted, 1)} of contacted` : undefined} />
        <KpiCell icon={RiErrorWarningLine} label="Failed sends" value={formatCompact(stats.emailsFailed)} context={stats.emailsFailed > 0 ? "Check the mailbox that sent them" : "None"} />
      </KpiStrip>

      <Frame className="lg:col-span-5">
        <FrameHeader title="Where leads stand" description="Every lead in the campaign, by where it is in the sequence." />
        <FramePanel>
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-paragraph-sm text-text-sub-600">
              <span className="text-title-h5 font-semibold tracking-tight text-text-strong-950">{formatPercent(progress, 1)}</span> of sends done
            </p>
            <p className="text-paragraph-xs tabular-nums text-text-sub-600">
              {stats.emailsSent.toLocaleString("en-US")} of {stats.emailsTotal.toLocaleString("en-US")}
            </p>
          </div>
          <div className="mb-5 mt-2 h-2 overflow-hidden rounded-full bg-bg-weak-50" role="progressbar" aria-label="Sends done" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: `${progress * 100}%`, backgroundColor: EMAIL }} />
          </div>
          <DonutChart items={leadStates} centerLabel="leads" emptyLabel="No leads yet" emptyDescription="Add leads to see where they stand." />
        </FramePanel>
      </Frame>

      <ChartCard
        className="lg:col-span-7"
        title="Send activity"
        description="Emails sent, still scheduled and failed, per day."
        actions={
          <SegmentedControl.Root value={String(range)} onValueChange={(v) => setRange(Number(v) as Range)}>
            <SegmentedControl.List className="w-auto">
              {RANGES.map((r) => (
                <SegmentedControl.Trigger key={r} value={String(r)} className="px-3">{r}d</SegmentedControl.Trigger>
              ))}
            </SegmentedControl.List>
          </SegmentedControl.Root>
        }
        legend={<SeriesStats items={sendStats} />}
        table={<TimeSeriesTable series={series} keys={SEND_KEYS} bucket="day" caption="Sends per day" />}
      >
        <TimeSeriesChart series={series} keys={SEND_KEYS} type="stackedBar" bucket="day" />
      </ChartCard>

      <Frame className="lg:col-span-12">
        <FrameHeader title="Sends by step" description="How many leads each step reached. Replies are campaign-wide — they aren't attributed to a step." />
        <FramePanel>
          {stepBreakdown.length === 0 ? (
            <EmptyChart height={140} title="Nothing sent yet" description="Steps fill in as the campaign sends." />
          ) : (
            <FunnelChart layout="tiles" stages={stepBreakdown.map((s) => ({ key: String(s.stepNumber), label: `Step ${s.stepNumber}`, value: s.sent }))} />
          )}
        </FramePanel>
      </Frame>
    </div>
  );
}
