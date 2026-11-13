"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  RiArchiveLine,
  RiBarChart2Line,
  RiCalendarCheckLine,
  RiErrorWarningLine,
  RiListOrdered2,
  RiLoader4Line,
  RiMoreLine,
  RiPauseCircleLine,
  RiPhoneLine,
  RiPlayCircleLine,
  RiRocketLine,
  RiSettings3Line,
  RiSmartphoneLine,
  RiTeamLine,
} from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Dropdown from "@/components/alignui/dropdown";
import { useDialogs } from "@/components/DialogProvider";
import { EmptyState } from "@/components/page/EmptyState";
import { PageHeader } from "@/components/page/PageHeader";
import { PageTabs } from "@/components/page/PageTabs";
import { Skeleton } from "@/components/page/Skeletons";
import { StatRow } from "@/components/page/StatRow";
import type { AiCampaignDetail, AiCampaignStats } from "@/lib/calls/aiCampaigns/api";
import { archiveAiCampaign, getAiCampaign, getAiCampaignStats, launchAiCampaign, updateAiCampaign } from "@/lib/calls/aiCampaigns/client";
import { cn } from "@/utils/cn";
import { AiAgentBadge, AiCampaignStateBadge, errorText } from "./aiShared";
import { AiCampaignOverview } from "./AiCampaignOverview";
import { AiLeadsTab } from "./AiLeadsTab";
import { AiSequenceTab } from "./AiSequenceTab";
import { AiSettingsTab } from "./AiSettingsTab";
import type { AiCampaignTab } from "./tabs";

const REFRESH_MS = 30_000;
const LIST = { href: "/calling/campaigns", label: "Call campaigns" };

export function AiCampaignDetailClient({ campaignId, initialTab }: { campaignId: string; initialTab: AiCampaignTab }) {
  const router = useRouter();
  const pathname = usePathname();
  const dialogs = useDialogs();
  const [tab, setTabState] = useState<AiCampaignTab>(initialTab);
  const [campaign, setCampaign] = useState<AiCampaignDetail | null>(null);
  const [stats, setStats] = useState<AiCampaignStats | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const setTab = (next: AiCampaignTab) => {
    setTabState(next);
    router.replace(next === "overview" ? pathname : `${pathname}?tab=${next}`, { scroll: false });
  };

  const load = useCallback(async () => {
    try {
      const [detail, nextStats] = await Promise.all([getAiCampaign(campaignId), getAiCampaignStats(campaignId).catch(() => null)]);
      setCampaign(detail);
      if (nextStats) setStats(nextStats);
      setLoadError(null);
    } catch (cause) {
      setLoadError(errorText(cause, "Could not load the campaign"));
    }
  }, [campaignId]);

  useEffect(() => {
    // Fetch on mount; state is set after the response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // A running campaign moves on its own; keep the figures fresh while the tab is visible.
  useEffect(() => {
    const timer = setInterval(() => { if (document.visibilityState === "visible") void load(); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  async function launch() {
    if (!campaign) return;
    setBusy(true);
    try {
      setCampaign(await launchAiCampaign(campaign.id));
      void load();
    } catch (cause) {
      await dialogs.alert({ title: "Could not launch the campaign", description: errorText(cause), variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function toggle() {
    if (!campaign) return;
    setBusy(true);
    try {
      setCampaign(await updateAiCampaign(campaign.id, { status: campaign.state === "active" ? "paused" : "active" }));
      void load();
    } catch (cause) {
      await dialogs.alert({ title: campaign.state === "active" ? "Could not pause the campaign" : "Could not resume the campaign", description: errorText(cause), variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!campaign) return;
    const ok = await dialogs.confirm({
      title: "Archive campaign?",
      description: "Calls and messages stop and the campaign leaves the list. Calls already placed stay on each lead, with their recordings and transcripts.",
      confirmLabel: "Archive campaign",
      variant: "error",
    });
    if (!ok) return;
    try {
      await archiveAiCampaign(campaign.id);
      router.push(LIST.href);
    } catch (cause) {
      await dialogs.alert({ title: "Could not archive the campaign", description: errorText(cause), variant: "error" });
    }
  }

  if (!campaign) {
    if (loadError) {
      return (
        <div className="mx-auto w-full max-w-[1440px]">
          <PageHeader back={LIST} title="AI calling campaign" />
          <EmptyState icon={RiErrorWarningLine} title="Could not load the campaign" description={loadError} action={<Button.Root variant="neutral" mode="stroke" size="small" onClick={() => void load()}>Try again</Button.Root>} />
        </div>
      );
    }
    return (
      <div aria-busy="true" aria-label="Loading" className="mx-auto w-full max-w-[1440px] space-y-6">
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-72 w-full rounded-2xl" />
      </div>
    );
  }

  const draft = campaign.state === "draft";
  const canLaunch = draft && !campaign.blocker;
  const numberNames = campaign.numbers.map((number) => number.name).join(", ");

  return (
    <div className="mx-auto w-full max-w-[1440px]">
      <PageHeader
        back={LIST}
        title={campaign.name}
        badge={
          <>
            <AiCampaignStateBadge state={campaign.state} />
            <AiAgentBadge />
          </>
        }
        description={<span suppressHydrationWarning>{`Created ${new Date(campaign.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} · ${campaign.stepCount} ${campaign.stepCount === 1 ? "step" : "steps"} in the sequence${campaign.description ? ` · ${campaign.description}` : ""}`}</span>}
        actions={
          <>
            {draft ? (
              <Button.Root variant="primary" mode="filled" size="small" onClick={() => void launch()} disabled={busy || !canLaunch} title={campaign.blocker ?? undefined}>
                <Button.Icon as={busy ? RiLoader4Line : RiRocketLine} className={cn(busy && "animate-spin")} />
                Launch
              </Button.Root>
            ) : (
              <Button.Root variant={campaign.state === "paused" ? "primary" : "neutral"} mode={campaign.state === "paused" ? "filled" : "stroke"} size="small" onClick={() => void toggle()} disabled={busy}>
                <Button.Icon as={busy ? RiLoader4Line : campaign.state === "active" ? RiPauseCircleLine : RiPlayCircleLine} className={cn(busy && "animate-spin")} />
                {campaign.state === "active" ? "Pause" : "Resume"}
              </Button.Root>
            )}
            <Dropdown.Root>
              <Dropdown.Trigger asChild>
                <Button.Root variant="neutral" mode="stroke" size="small" aria-label="More actions"><Button.Icon as={RiMoreLine} /></Button.Root>
              </Dropdown.Trigger>
              <Dropdown.Content align="end">
                <Dropdown.Item destructive onSelect={() => void archive()}>
                  <Dropdown.ItemIcon as={RiArchiveLine} />
                  Archive campaign
                </Dropdown.Item>
              </Dropdown.Content>
            </Dropdown.Root>
          </>
        }
      />
      {draft && campaign.blocker && <p className="mt-3 text-paragraph-xs text-text-sub-600">Cannot launch yet: {campaign.blocker.charAt(0).toLowerCase()}{campaign.blocker.slice(1)}.</p>}
      {draft && !campaign.blocker && <p className="mt-3 text-paragraph-xs text-text-sub-600">This campaign is a draft and places nothing until you launch it.</p>}

      <StatRow
        className="mt-5"
        items={[
          { label: "Leads", value: campaign.leads.toLocaleString("en-US"), icon: RiTeamLine, hint: "People enrolled in this campaign" },
          { label: "Calls today", value: `${campaign.callsToday.toLocaleString("en-US")}${campaign.callsPerDayLimit ? ` / ${campaign.callsPerDayLimit.toLocaleString("en-US")}` : ""}`, icon: RiPhoneLine, hint: "Calls placed today, against what the campaign's numbers may place a day" },
          { label: "Booked", value: campaign.booked.toLocaleString("en-US"), icon: RiCalendarCheckLine, hint: "Meetings booked by leads of this campaign" },
          { label: "Numbers", value: campaign.numbers.length.toLocaleString("en-US"), icon: RiSmartphoneLine, hint: numberNames || "No calling numbers assigned" },
        ]}
      />

      <PageTabs
        className="mt-6"
        label="Campaign sections"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "overview", label: "Overview", icon: RiBarChart2Line },
          { value: "leads", label: "Leads", icon: RiTeamLine, count: campaign.leads },
          { value: "sequence", label: "Sequence", icon: RiListOrdered2, count: campaign.stepCount },
          { value: "settings", label: "Settings", icon: RiSettings3Line },
        ]}
      />

      {/* Leads, Sequence and Settings stay mounted when hidden, so filters and unsaved edits survive a trip to another tab. */}
      <div role="tabpanel" className="mt-6">
        {tab === "overview" && <AiCampaignOverview campaign={campaign} stats={stats} />}
        <div hidden={tab !== "leads"}>
          <AiLeadsTab campaignId={campaign.id} counts={stats?.byStatus ?? null} total={campaign.leads} onChanged={() => void load()} />
        </div>
        <div hidden={tab !== "sequence"}>
          <AiSequenceTab campaign={campaign} stats={stats?.perStep} onSaved={() => void load()} />
        </div>
        <div hidden={tab !== "settings"}>
          <AiSettingsTab campaign={campaign} onSaved={() => void load()} onToggle={() => void toggle()} onArchive={() => void archive()} toggling={busy} />
        </div>
      </div>
    </div>
  );
}
