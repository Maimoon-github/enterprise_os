"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  RiArrowLeftSLine,
  RiArrowRightSLine,
  RiChat1Line,
  RiDeleteBinLine,
  RiErrorWarningLine,
  RiExternalLinkLine,
  RiFileExcel2Line,
  RiLoader4Line,
  RiMoreLine,
  RiPlayCircleLine,
  RiSearchLine,
  RiStopCircleLine,
  RiTeamLine,
  RiUserAddLine,
} from "@remixicon/react";
import * as Badge from "@/components/alignui/badge";
import * as Button from "@/components/alignui/button";
import * as Dropdown from "@/components/alignui/dropdown";
import * as Input from "@/components/alignui/input";
import * as SegmentedControl from "@/components/alignui/segmented-control";
import * as Table from "@/components/alignui/table";
import { Frame, FrameHeader, FramePanel } from "@/components/analytics/kit/Frame";
import { useDialogs } from "@/components/DialogProvider";
import AddPeopleToCampaignModal from "@/components/leads/AddPeopleToCampaignModal";
import CampaignCsvMappingDialog from "@/components/leads/CampaignCsvMappingDialog";
import { EmptyState } from "@/components/page/EmptyState";
import { Skeleton } from "@/components/page/Skeletons";
import {
  WHATSAPP_CAMPAIGN_LEAD_STATUSES,
  type ListWhatsappCampaignLeadsResponse,
  type UpdateWhatsappCampaignLeadRequest,
  type WhatsappCampaignImportResponse,
  type WhatsappCampaignLead,
  type WhatsappCampaignLeadStatus,
  type WhatsappCampaignStats,
} from "@/lib/whatsapp/campaigns/contract";
import { cn } from "@/utils/cn";
import { apiJson, errorText } from "./api";
import { LEAD_STATUS, relativeTime } from "./metrics";

const PAGE_SIZE = 25;

type StatusFilter = WhatsappCampaignLeadStatus | "all";

/** "Message 2 of 3": how far the sequence has got for this lead. */
function progressLabel(lead: WhatsappCampaignLead, stepCount: number): string {
  if (lead.status === "queued") return `Message 1 of ${stepCount}`;
  if (lead.status === "in_sequence") return `Message ${Math.min(lead.currentStep + 1, stepCount)} of ${stepCount}`;
  return `${lead.currentStep} of ${stepCount} sent`;
}

function nextOrLast(lead: WhatsappCampaignLead): string {
  if (lead.status === "queued" || lead.status === "in_sequence") {
    return lead.nextSendAt ? `Next ${relativeTime(lead.nextSendAt)}` : "Waiting for a number";
  }
  if (lead.status === "replied") return lead.repliedAt ? `Replied ${relativeTime(lead.repliedAt)}` : "Replied";
  return lead.lastSentAt ? `Last sent ${relativeTime(lead.lastSentAt)}` : "Nothing sent";
}

/**
 * The Leads tab of a message campaign: import (spreadsheet or People),
 * filter by status and search, and stop, resume or remove a lead. Owns its
 * page of leads and tells the parent when counts may have changed.
 */
export function WhatsappCampaignLeadsTab({
  campaignId,
  stats,
  stepCount,
  onChanged,
}: {
  campaignId: string;
  stats: WhatsappCampaignStats;
  stepCount: number;
  /** Leads were added, removed or changed; the parent reloads the campaign's figures. */
  onChanged: () => void;
}) {
  const dialogs = useDialogs();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListWhatsappCampaignLeadsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [showPeople, setShowPeople] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => { setDebounced(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
    if (status !== "all") params.set("status", status);
    if (debounced) params.set("q", debounced);
    try {
      const result = await apiJson<ListWhatsappCampaignLeadsResponse>(`/api/whatsapp/campaigns/${campaignId}/leads?${params}`);
      setData(result);
      setLoadError(null);
    } catch (cause) {
      setLoadError(errorText(cause, "Could not load leads"));
    } finally {
      setLoading(false);
    }
  }, [campaignId, page, status, debounced]);

  useEffect(() => {
    // Fetch on mount and whenever the query changes; state is set after the response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // Counts or the sequence moved on elsewhere (a poll of the detail page): refresh this page too.
  const totalSeen = useRef(stats.total);
  useEffect(() => {
    if (totalSeen.current !== stats.total) {
      totalSeen.current = stats.total;
      void load();
    }
  }, [stats.total, load]);

  const refreshAll = useCallback(() => {
    void load();
    onChanged();
  }, [load, onChanged]);

  async function act(lead: WhatsappCampaignLead, action: UpdateWhatsappCampaignLeadRequest["action"]) {
    setBusyId(lead.id);
    try {
      await apiJson(`/api/whatsapp/campaigns/${campaignId}/leads/${lead.id}`, { method: "PATCH", body: JSON.stringify({ action } satisfies UpdateWhatsappCampaignLeadRequest) });
      refreshAll();
    } catch (cause) {
      await dialogs.alert({ title: action === "stop" ? "Could not stop the lead" : "Could not resume the lead", description: errorText(cause), variant: "error" });
    } finally {
      setBusyId(null);
    }
  }

  async function remove(lead: WhatsappCampaignLead) {
    const ok = await dialogs.confirm({
      title: "Remove lead?",
      description: `${lead.name || lead.phone} leaves this campaign and gets no more messages. Messages already sent stay in Messages and the CRM.`,
      confirmLabel: "Remove lead",
      variant: "error",
    });
    if (!ok) return;
    setBusyId(lead.id);
    try {
      await apiJson(`/api/whatsapp/campaigns/${campaignId}/leads/${lead.id}`, { method: "DELETE" });
      refreshAll();
    } catch (cause) {
      await dialogs.alert({ title: "Could not remove the lead", description: errorText(cause), variant: "error" });
    } finally {
      setBusyId(null);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;
  const filtering = status !== "all" || debounced.length > 0;
  const openStatuses = new Set<WhatsappCampaignLeadStatus>(["queued", "in_sequence"]);

  const importActions = (
    <>
      <Button.Root variant="neutral" mode="stroke" size="small" onClick={() => fileRef.current?.click()}>
        <Button.Icon as={RiFileExcel2Line} />
        Import spreadsheet
      </Button.Root>
      <Button.Root variant="neutral" mode="stroke" size="small" onClick={() => setShowPeople(true)}>
        <Button.Icon as={RiUserAddLine} />
        Add from People
      </Button.Root>
    </>
  );

  return (
    <Frame>
      <FrameHeader
        title="Leads"
        description="Everyone enrolled in this campaign and where they are in the sequence."
        actions={<div className="flex flex-wrap items-center gap-2">{importActions}</div>}
      />
      <FramePanel className="p-2 sm:p-2">
        <div className="flex flex-col gap-2 p-2 lg:flex-row lg:items-center lg:justify-between">
          <div className="overflow-x-auto">
            <SegmentedControl.Root value={status} onValueChange={(v) => { setStatus(v as StatusFilter); setPage(1); }}>
              <SegmentedControl.List className="w-auto">
                <SegmentedControl.Trigger value="all" className="gap-1.5 px-3">
                  All <span className="tabular-nums text-text-soft-400">{stats.total}</span>
                </SegmentedControl.Trigger>
                {WHATSAPP_CAMPAIGN_LEAD_STATUSES.map((s) => (
                  <SegmentedControl.Trigger key={s} value={s} className="gap-1.5 px-3">
                    {LEAD_STATUS[s].label} <span className="tabular-nums text-text-soft-400">{stats[s]}</span>
                  </SegmentedControl.Trigger>
                ))}
              </SegmentedControl.List>
            </SegmentedControl.Root>
          </div>
          <Input.Root size="small" className="w-full lg:w-64">
            <Input.Wrapper>
              <Input.Icon as={RiSearchLine} />
              <Input.Input type="search" aria-label="Search leads" placeholder="Search name, phone, company…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </Input.Wrapper>
          </Input.Root>
        </div>

        {notice && (
          <p role="status" className="mx-2 mb-2 rounded-xl bg-bg-weak-50 px-3 py-2 text-paragraph-xs text-text-sub-600 ring-1 ring-inset ring-stroke-soft-200">{notice}</p>
        )}

        <div className="overflow-x-auto">
          {loading ? (
            <div aria-busy="true" aria-label="Loading" className="space-y-2 p-2">
              {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12 w-full rounded-xl" />)}
            </div>
          ) : loadError ? (
            <EmptyState icon={RiErrorWarningLine} title="Could not load leads" description={loadError} action={<Button.Root variant="neutral" mode="stroke" size="small" onClick={() => { setLoading(true); void load(); }}>Try again</Button.Root>} />
          ) : !data || data.leads.length === 0 ? (
            filtering ? (
              <EmptyState icon={RiSearchLine} title="No leads match" description="Try another status or search." action={<Button.Root variant="neutral" mode="stroke" size="small" onClick={() => { setSearch(""); setStatus("all"); }}>Clear filters</Button.Root>} />
            ) : (
              <EmptyState
                icon={RiTeamLine}
                title="No leads yet"
                description="Import a spreadsheet with phone numbers, or add people from your lead database."
                action={<div className="flex flex-wrap justify-center gap-2">{importActions}</div>}
              />
            )
          ) : (
            <Table.Root className="min-w-[860px] [&>table]:table-fixed">
              <Table.Header>
                <Table.Row>
                  <Table.Head scope="col" className="px-4">Lead</Table.Head>
                  <Table.Head scope="col" className="w-40 px-4">Phone</Table.Head>
                  <Table.Head scope="col" className="w-32 px-4">Status</Table.Head>
                  <Table.Head scope="col" className="w-36 px-4">Progress</Table.Head>
                  <Table.Head scope="col" className="w-44 px-4">When</Table.Head>
                  <Table.Head scope="col" className="w-14 px-4"><span className="sr-only">Actions</span></Table.Head>
                </Table.Row>
              </Table.Header>
              <Table.Body spacing={4}>
                {data.leads.map((lead) => {
                  const meta = LEAD_STATUS[lead.status];
                  const busy = busyId === lead.id;
                  return (
                    <Table.Row key={lead.id} aria-busy={busy || undefined} className={cn(busy && "pointer-events-none opacity-60")}>
                      <Table.Cell className="px-4">
                        <p className="truncate text-label-sm text-text-strong-950" title={lead.name ?? undefined}>{lead.name || "Unnamed"}</p>
                        <p className="mt-0.5 truncate text-paragraph-xs text-text-sub-600">{[lead.title, lead.companyName].filter(Boolean).join(" · ") || "—"}</p>
                      </Table.Cell>
                      <Table.Cell className="px-4 text-paragraph-sm tabular-nums text-text-sub-600">{lead.phone}</Table.Cell>
                      <Table.Cell className="px-4">
                        <Badge.Root size="small" variant="lighter" color={meta.color}>
                          <Badge.Dot />
                          {meta.label}
                        </Badge.Root>
                      </Table.Cell>
                      <Table.Cell className="px-4 text-paragraph-sm tabular-nums text-text-sub-600">{progressLabel(lead, stepCount)}</Table.Cell>
                      <Table.Cell className="px-4">
                        <p className="text-paragraph-sm text-text-sub-600" suppressHydrationWarning>{nextOrLast(lead)}</p>
                        {lead.status === "failed" && lead.lastError && (
                          <p className="mt-0.5 line-clamp-2 text-paragraph-xs text-error-base" title={lead.lastError}>{lead.lastError}</p>
                        )}
                      </Table.Cell>
                      <Table.Cell className="px-4">
                        <div className="flex justify-end">
                          <Dropdown.Root>
                            <Dropdown.Trigger asChild>
                              <Button.Root variant="neutral" mode="ghost" size="xsmall" disabled={busy} aria-label={`More actions for ${lead.name || lead.phone}`}>
                                <Button.Icon as={busy ? RiLoader4Line : RiMoreLine} className={cn(busy && "animate-spin")} />
                              </Button.Root>
                            </Dropdown.Trigger>
                            <Dropdown.Content>
                              {openStatuses.has(lead.status) && (
                                <Dropdown.Item onSelect={() => void act(lead, "stop")}>
                                  <Dropdown.ItemIcon as={RiStopCircleLine} />
                                  Stop sequence
                                </Dropdown.Item>
                              )}
                              {(lead.status === "stopped" || lead.status === "failed") && (
                                <Dropdown.Item onSelect={() => void act(lead, "resume")}>
                                  <Dropdown.ItemIcon as={RiPlayCircleLine} />
                                  Resume sequence
                                </Dropdown.Item>
                              )}
                              {lead.chatId && (
                                <Dropdown.Item onSelect={() => router.push(`/calling/messages?chat=${encodeURIComponent(lead.chatId!)}`)}>
                                  <Dropdown.ItemIcon as={RiChat1Line} />
                                  Open chat
                                  <Dropdown.ItemIcon as={RiExternalLinkLine} className="ml-auto" />
                                </Dropdown.Item>
                              )}
                              <Dropdown.Separator />
                              <Dropdown.Item destructive onSelect={() => void remove(lead)}>
                                <Dropdown.ItemIcon as={RiDeleteBinLine} />
                                Remove from campaign
                              </Dropdown.Item>
                            </Dropdown.Content>
                          </Dropdown.Root>
                        </div>
                      </Table.Cell>
                    </Table.Row>
                  );
                })}
              </Table.Body>
            </Table.Root>
          )}
        </div>

        {data && data.total > data.pageSize && (
          <div className="flex items-center justify-between gap-3 px-3 pb-2 pt-3">
            <p className="text-paragraph-xs tabular-nums text-text-sub-600">
              {((data.page - 1) * data.pageSize + 1).toLocaleString("en-US")}–{Math.min(data.page * data.pageSize, data.total).toLocaleString("en-US")} of {data.total.toLocaleString("en-US")}
            </p>
            <div className="flex items-center gap-1">
              <Button.Root variant="neutral" mode="stroke" size="xsmall" disabled={data.page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} aria-label="Previous page">
                <Button.Icon as={RiArrowLeftSLine} />
              </Button.Root>
              <span className="px-2 text-paragraph-xs tabular-nums text-text-sub-600">Page {data.page} of {pages}</span>
              <Button.Root variant="neutral" mode="stroke" size="xsmall" disabled={data.page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                <Button.Icon as={RiArrowRightSLine} />
              </Button.Root>
            </div>
          </div>
        )}
      </FramePanel>

      <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(event) => setPendingFile(event.target.files?.[0] ?? null)} />
      {pendingFile && (
        <CampaignCsvMappingDialog
          file={pendingFile}
          endpoint={`/api/whatsapp/campaigns/${campaignId}/upload`}
          channel="whatsapp"
          onClose={() => { setPendingFile(null); if (fileRef.current) fileRef.current.value = ""; }}
          onImported={(result) => {
            const imported = result as WhatsappCampaignImportResponse;
            setNotice(importSummary(imported));
            setPendingFile(null);
            if (fileRef.current) fileRef.current.value = "";
            refreshAll();
          }}
        />
      )}
      {showPeople && (
        <AddPeopleToCampaignModal
          campaignId={campaignId}
          channel="whatsapp"
          onClose={() => setShowPeople(false)}
          onAdded={(result) => {
            setNotice(`${result.added} added from People${result.skippedDuplicate ? ` · ${result.skippedDuplicate} already in the campaign` : ""}${result.skippedMissingIdentity ? ` · ${result.skippedMissingIdentity} without a phone number` : ""}`);
            refreshAll();
          }}
        />
      )}
    </Frame>
  );
}

export function importSummary(result: WhatsappCampaignImportResponse): string {
  const parts = [`${result.added.toLocaleString("en-US")} added`];
  if (result.alreadyInCampaign) parts.push(`${result.alreadyInCampaign.toLocaleString("en-US")} already in the campaign`);
  if (result.skipped.length) parts.push(`${result.skipped.length} skipped (${result.skipped[0]}${result.skipped.length > 1 ? ", …" : ""})`);
  return parts.join(" · ");
}
