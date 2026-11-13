"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  RiArchiveLine,
  RiBarChart2Line,
  RiErrorWarningLine,
  RiHourglassLine,
  RiListOrdered2,
  RiLoader4Line,
  RiMoreLine,
  RiPauseCircleLine,
  RiPencilLine,
  RiPlayCircleLine,
  RiSmartphoneLine,
  RiTeamLine,
  RiTimeLine,
} from "@remixicon/react";
import * as Badge from "@/components/alignui/badge";
import * as Button from "@/components/alignui/button";
import * as Dropdown from "@/components/alignui/dropdown";
import { useDialogs } from "@/components/DialogProvider";
import { EmptyState } from "@/components/page/EmptyState";
import { PageHeader } from "@/components/page/PageHeader";
import { PageTabs } from "@/components/page/PageTabs";
import { Skeleton } from "@/components/page/Skeletons";
import { StatRow } from "@/components/page/StatRow";
import type { UpdateWhatsappCampaignRequest, WhatsappCampaignDetail } from "@/lib/whatsapp/campaigns/contract";
import { cn } from "@/utils/cn";
import { apiJson, errorText } from "./api";
import { EditWhatsappCampaignModal } from "./EditWhatsappCampaignModal";
import { CAMPAIGN_STATUS, campaignFunnel, launchBlocker } from "./metrics";
import { WhatsappCampaignLeadsTab } from "./WhatsappCampaignLeadsTab";
import { WhatsappCampaignOverview } from "./WhatsappCampaignOverview";
import { WhatsappSequenceEditor } from "./WhatsappSequenceEditor";

export type CampaignTab = "overview" | "leads" | "sequence";

const REFRESH_MS = 30_000;

function createdLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function WhatsappCampaignDetailClient({ campaignId, initialTab }: { campaignId: string; initialTab: CampaignTab }) {
  const router = useRouter();
  const pathname = usePathname();
  const dialogs = useDialogs();
  const [tab, setTabState] = useState<CampaignTab>(initialTab);
  const [campaign, setCampaign] = useState<WhatsappCampaignDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);
  const [editing, setEditing] = useState(false);

  // The tab lives in the URL (?tab=leads), so a link or a reload lands on it.
  const setTab = (next: CampaignTab) => {
    setTabState(next);
    router.replace(next === "overview" ? pathname : `${pathname}?tab=${next}`, { scroll: false });
  };

  const load = useCallback(async () => {
    try {
      setCampaign(await apiJson<WhatsappCampaignDetail>(`/api/whatsapp/campaigns/${campaignId}`));
      setLoadError(null);
    } catch (cause) {
      setLoadError(errorText(cause, "Could not load the campaign"));
    }
  }, [campaignId]);

  useEffect(() => {
    // Fetch on mount and whenever the query changes; state is set after the response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // A running campaign moves on its own; keep the figures fresh while the tab is visible.
  useEffect(() => {
    const timer = setInterval(() => { if (document.visibilityState === "visible") void load(); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const funnel = useMemo(() => (campaign ? campaignFunnel(campaign.stats) : null), [campaign]);

  async function toggleStatus() {
    if (!campaign) return;
    const next = campaign.status === "active" ? "paused" : "active";
    setToggling(true);
    try {
      const request: UpdateWhatsappCampaignRequest = { status: next };
      await apiJson(`/api/whatsapp/campaigns/${campaign.id}`, { method: "PATCH", body: JSON.stringify(request) });
      setCampaign((prev) => (prev ? { ...prev, status: next } : prev));
      void load();
    } catch (cause) {
      await dialogs.alert({ title: next === "paused" ? "Could not pause the campaign" : "Could not launch the campaign", description: errorText(cause), variant: "error" });
    } finally {
      setToggling(false);
    }
  }

  async function archive() {
    if (!campaign) return;
    const ok = await dialogs.confirm({
      title: "Archive campaign?",
      description: "Sending stops and the campaign leaves the list. Messages already sent stay in Messages and the CRM.",
      confirmLabel: "Archive campaign",
      variant: "error",
    });
    if (!ok) return;
    try {
      await apiJson(`/api/whatsapp/campaigns/${campaign.id}`, { method: "DELETE" });
      router.push("/whatsapp/campaigns");
    } catch (cause) {
      await dialogs.alert({ title: "Could not archive campaign", description: errorText(cause), variant: "error" });
    }
  }

  if (!campaign || !funnel) {
    if (loadError) {
      return (
        <div className="mx-auto w-full max-w-[1440px]">
          <PageHeader back={{ href: "/whatsapp/campaigns", label: "Message campaigns" }} title="Message campaign" />
          <EmptyState
            icon={RiErrorWarningLine}
            title="Could not load the campaign"
            description={loadError}
            action={<Button.Root variant="neutral" mode="stroke" size="small" onClick={() => void load()}>Try again</Button.Root>}
          />
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

  const status = CAMPAIGN_STATUS[campaign.status];
  const connected = campaign.senders.filter((s) => s.status === "connected").length;
  const blocker = campaign.status === "paused" ? launchBlocker({ connectedSenders: connected, leads: campaign.stats.total, firstMessage: campaign.steps[0]?.body }) : null;
  const senderNames = campaign.senders.map((s) => s.name || s.phone || "Number").join(", ");

  return (
    <div className="mx-auto w-full max-w-[1440px]">
      <PageHeader
        back={{ href: "/whatsapp/campaigns", label: "Message campaigns" }}
        title={campaign.name}
        badge={
          <Badge.Root size="medium" variant="lighter" color={status.color}>
            <Badge.Dot />
            {status.label}
          </Badge.Root>
        }
        description={<span suppressHydrationWarning>{`Created ${createdLabel(campaign.createdAt)} · ${campaign.stepCount} ${campaign.stepCount === 1 ? "message" : "messages"} in the sequence${campaign.description ? ` · ${campaign.description}` : ""}`}</span>}
        actions={
          <>
            <Button.Root
              variant={campaign.status === "paused" ? "primary" : "neutral"}
              mode={campaign.status === "paused" ? "filled" : "stroke"}
              size="small"
              onClick={() => void toggleStatus()}
              disabled={toggling || Boolean(blocker)}
              title={blocker ?? undefined}
            >
              <Button.Icon as={toggling ? RiLoader4Line : campaign.status === "active" ? RiPauseCircleLine : RiPlayCircleLine} className={cn(toggling && "animate-spin")} />
              {campaign.status === "active" ? "Pause" : campaign.stats.messagesSent > 0 ? "Resume" : "Launch"}
            </Button.Root>
            <Dropdown.Root>
              <Dropdown.Trigger asChild>
                <Button.Root variant="neutral" mode="stroke" size="small" aria-label="More actions">
                  <Button.Icon as={RiMoreLine} />
                </Button.Root>
              </Dropdown.Trigger>
              <Dropdown.Content>
                <Dropdown.Item onSelect={() => setEditing(true)}>
                  <Dropdown.ItemIcon as={RiPencilLine} />
                  Edit campaign
                </Dropdown.Item>
                <Dropdown.Separator />
                <Dropdown.Item destructive onSelect={() => void archive()}>
                  <Dropdown.ItemIcon as={RiArchiveLine} />
                  Archive campaign
                </Dropdown.Item>
              </Dropdown.Content>
            </Dropdown.Root>
          </>
        }
      />
      {blocker && <p className="mt-3 text-paragraph-xs text-text-sub-600">Cannot launch yet: {blocker.charAt(0).toLowerCase()}{blocker.slice(1)}.</p>}

      <StatRow
        className="mt-5"
        items={[
          { label: "Queued", value: funnel.queued.toLocaleString("en-US"), icon: RiTimeLine, hint: "Leads still waiting for their first message" },
          { label: "In sequence", value: funnel.inSequence.toLocaleString("en-US"), icon: RiHourglassLine, hint: "Leads with follow-ups still to come" },
          { label: "Numbers", value: campaign.senders.length.toLocaleString("en-US"), icon: RiSmartphoneLine, hint: senderNames || "No WhatsApp numbers assigned" },
        ]}
      />

      <PageTabs
        className="mt-6"
        label="Campaign sections"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "overview", label: "Overview", icon: RiBarChart2Line },
          { value: "leads", label: "Leads", icon: RiTeamLine, count: campaign.stats.total },
          { value: "sequence", label: "Sequence", icon: RiListOrdered2, count: campaign.stepCount },
        ]}
      />

      {/* Leads and Sequence stay mounted when hidden, so filters and unsaved
          sequence edits survive a trip to another tab. */}
      <div role="tabpanel" className="mt-6">
        {tab === "overview" && <WhatsappCampaignOverview funnel={funnel} campaign={campaign} />}
        <div hidden={tab !== "leads"}>
          <WhatsappCampaignLeadsTab campaignId={campaign.id} stats={campaign.stats} stepCount={campaign.stepCount} onChanged={() => void load()} />
        </div>
        <div hidden={tab !== "sequence"}>
          <WhatsappSequenceEditor
            campaignId={campaign.id}
            initialSteps={campaign.steps}
            sentByStep={campaign.sentByStep}
            leadsVersion={campaign.stats.total}
            onSaved={() => void load()}
          />
        </div>
      </div>

      <EditWhatsappCampaignModal campaign={campaign} open={editing} onOpenChange={setEditing} onSaved={() => { setEditing(false); void load(); }} />
    </div>
  );
}
