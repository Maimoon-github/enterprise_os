"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRefreshOnReturn } from "./useRefreshOnReturn";
import {
  RiAddLine,
  RiArrowLeftSLine,
  RiCalendarTodoLine,
  RiCheckDoubleLine,
  RiDeleteBinLine,
  RiFileTextLine,
  RiLinkedinBoxFill,
  RiLoader4Line,
  RiMicLine,
  RiMoreLine,
  RiPauseCircleLine,
  RiPencilLine,
  RiPhoneLine,
  RiPlayCircleLine,
  RiRepeatLine,
  RiSearchLine,
  RiTeamLine,
  RiTimeLine,
  RiUpload2Line,
  RiUserReceivedLine,
} from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Dropdown from "@/components/alignui/dropdown";
import * as Input from "@/components/alignui/input";
import * as Modal from "@/components/alignui/modal";
import * as Table from "@/components/alignui/table";
import { ErrorState } from "@/components/analytics/kit/ErrorState";
import { Frame, FrameHeader, FramePanel } from "@/components/analytics/kit/Frame";
import { formatPercent } from "@/components/analytics/theme";
import { EmptyState } from "@/components/page/EmptyState";
import { PageHeader } from "@/components/page/PageHeader";
import { PageTabs } from "@/components/page/PageTabs";
import { StatRow } from "@/components/page/StatRow";
import { errorMessage, timeAgo } from "@/components/crm/crm-utils";
import { CallButton } from "@/components/calls/CallButton";
import { FormError, TextField } from "@/components/calls/fields";
import { CallingDetailSkeleton } from "@/components/calling/CallingSkeletons";
import { CompanyNameField } from "@/components/calling/CompanyNameField";
import { ContactPanel, RemoveContactModal } from "@/components/calling/ContactPanel";
import { EditContactModal } from "@/components/calling/EditContactModal";
import { EditCampaignModal, DeleteCampaignModal } from "@/components/calling/CampaignModals";
import { addCampaignContact, getCampaign, importCampaignContacts, updateCampaign } from "@/lib/calls/client";
import { CAMPAIGN_CONTACT_STAGE_LABELS, type CampaignContact, type CampaignSummary } from "@/lib/calls/contract";
import { Avatar, CallStatusBadge, CampaignStatusBadge, CompanyFavicon, LeadStagePicker, attemptHint, bareDomain, followUpHint, titleAtCompany, useCrmCategories } from "@/components/calling/callingShared";
import { CONTACT_TABS, inTab, isOverdue, type ContactTab } from "@/components/calling/contactTabs";
import { cn } from "@/utils/cn";

const TAB_LABELS: Record<ContactTab, string> = {
  all: "All leads",
  due: "Due today",
  follow_up: CAMPAIGN_CONTACT_STAGE_LABELS.follow_up,
  done: CAMPAIGN_CONTACT_STAGE_LABELS.done,
};
const TAB_ICONS: Record<ContactTab, React.ComponentType<{ className?: string }>> = {
  all: RiTeamLine,
  due: RiCalendarTodoLine,
  follow_up: RiRepeatLine,
  done: RiCheckDoubleLine,
};
const TAB_DESCRIPTIONS: Record<ContactTab, string> = {
  all: "Everyone in this campaign. Select a person to see their calls, notes and WhatsApp.",
  due: "Not called yet, retries that have come round, and follow-ups due today or overdue.",
  follow_up: "You spoke to them; the next step is pending.",
  done: "Finished: no more calls are planned.",
};
const TABS = CONTACT_TABS;

function createdOn(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function matches(contact: CampaignContact, term: string): boolean {
  if (!term) return true;
  const { fullName, firstName, companyName, companyWebsite, phone, email, title } = contact.person;
  return [fullName, firstName, companyName, companyWebsite, phone, email, title].some((field) => field?.toLowerCase().includes(term));
}

export default function CampaignClient({ campaignId, initialTab = "all" }: { campaignId: string; initialTab?: ContactTab }) {
  const router = useRouter();
  const [campaign, setCampaign] = useState<CampaignSummary | null>(null);
  const [contacts, setContacts] = useState<CampaignContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTabState] = useState<ContactTab>(initialTab);
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [actionError, setActionError] = useState("");
  const [openContactId, setOpenContactId] = useState<string | null>(null);
  const [editingContact, setEditingContact] = useState<CampaignContact | null>(null);
  const [removingContact, setRemovingContact] = useState<CampaignContact | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await getCampaign(campaignId);
      setCampaign(response.campaign);
      setContacts(response.contacts);
      setError("");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [campaignId]);

  useEffect(() => {
    setLoading(true);
    void load();
  }, [load]);

  // Every reload after the first keeps the rows on screen, dimmed.
  const reload = useCallback(() => {
    setRefreshing(true);
    return load();
  }, [load]);
  useRefreshOnReturn(reload);

  // The tab lives in the URL (?tab=due) so a reload or a shared link lands on it.
  const setTab = (next: ContactTab) => {
    setTabState(next);
    const url = new URL(window.location.href);
    if (next === "all") url.searchParams.delete("tab");
    else url.searchParams.set("tab", next);
    window.history.replaceState(window.history.state, "", url);
  };

  const categories = useCrmCategories();
  const total = contacts.length;
  // Fixed per load, so "due today" and "overdue" don't read the clock on every render.
  const now = useMemo(() => new Date(), [contacts]); // eslint-disable-line react-hooks/exhaustive-deps
  const tabCounts = useMemo(
    () => Object.fromEntries(TABS.map((key) => [key, contacts.filter((contact) => inTab(contact, key, now)).length])) as Record<ContactTab, number>,
    [contacts, now],
  );
  const term = search.trim().toLowerCase();
  const inCurrentTab = useMemo(() => contacts.filter((contact) => inTab(contact, tab, now)), [contacts, tab, now]);
  const visibleContacts = useMemo(() => inCurrentTab.filter((contact) => matches(contact, term)), [inCurrentTab, term]);
  const replaceContact = useCallback((updated: CampaignContact) => {
    setContacts((current) => current.map((contact) => (contact.id === updated.id ? updated : contact)));
  }, []);

  const pulse = useMemo(() => {
    const overdue = contacts.filter((contact) => contact.stage !== "done" && isOverdue(contact.followUpAt, now)).length;
    const lastCalledAt = contacts.reduce<string | null>((latest, contact) => (contact.lastCalledAt && (!latest || contact.lastCalledAt > latest) ? contact.lastCalledAt : latest), null);
    return { overdue, lastCalledAt };
  }, [contacts, now]);

  const toggleStatus = async () => {
    if (!campaign) return;
    setToggling(true);
    setActionError("");
    try {
      setCampaign(await updateCampaign(campaign.id, { status: campaign.status === "active" ? "paused" : "active" }));
    } catch (cause) {
      setActionError(errorMessage(cause));
    } finally {
      setToggling(false);
    }
  };

  if (loading) return <CallingDetailSkeleton />;

  if (!campaign) {
    return (
      <div className="mx-auto w-full max-w-[1440px] space-y-4">
        <Link href="/calling/campaigns" className="-ml-1 inline-flex items-center gap-0.5 rounded-md px-1 text-label-xs text-text-sub-600 hover:text-text-strong-950">
          <RiArrowLeftSLine className="size-4" aria-hidden="true" />
          Call campaigns
        </Link>
        <ErrorState message={error || "This campaign could not be loaded."} onRetry={() => { setLoading(true); void load(); }} />
      </div>
    );
  }

  const { leads, called, connected } = campaign.stats;
  const uploadButton = (
    <Button.Root variant="neutral" mode="stroke" size="small" onClick={() => setUploadOpen(true)}>
      <Button.Icon as={RiUpload2Line} />
      Upload contacts
    </Button.Root>
  );
  const addButton = (
    <Button.Root variant="primary" mode="filled" size="small" onClick={() => setAddOpen(true)}>
      <Button.Icon as={RiAddLine} />
      Add contact
    </Button.Root>
  );

  return (
    <div className="mx-auto w-full max-w-[1440px]">
      <PageHeader
        back={{ href: "/calling/campaigns", label: "Call campaigns" }}
        title={campaign.name}
        badge={<CampaignStatusBadge status={campaign.status} />}
        description={
          <span suppressHydrationWarning>
            {campaign.description ? `${campaign.description} · ` : ""}
            {total.toLocaleString("en-US")} {total === 1 ? "contact" : "contacts"} · Created {createdOn(campaign.createdAt)}
          </span>
        }
        actions={
          <>
            {uploadButton}
            {addButton}
            <Dropdown.Root>
              <Dropdown.Trigger asChild>
                <Button.Root variant="neutral" mode="stroke" size="small" disabled={toggling} aria-label={`More actions for ${campaign.name}`}>
                  <Button.Icon as={RiMoreLine} />
                </Button.Root>
              </Dropdown.Trigger>
              <Dropdown.Content align="end">
                <Dropdown.Item onSelect={() => setEditOpen(true)}>
                  <Dropdown.ItemIcon as={RiPencilLine} />
                  Edit campaign
                </Dropdown.Item>
                <Dropdown.Item onSelect={() => void toggleStatus()} disabled={toggling}>
                  <Dropdown.ItemIcon as={campaign.status === "active" ? RiPauseCircleLine : RiPlayCircleLine} />
                  {campaign.status === "active" ? "Pause campaign" : "Resume campaign"}
                </Dropdown.Item>
                <Dropdown.Separator />
                <Dropdown.Item destructive onSelect={() => setDeleteOpen(true)}>
                  <Dropdown.ItemIcon as={RiDeleteBinLine} />
                  Delete campaign
                </Dropdown.Item>
              </Dropdown.Content>
            </Dropdown.Root>
          </>
        }
      />
      {(actionError || (error && !refreshing)) && <FormError className="mt-3">{actionError || error}</FormError>}

      <StatRow
        className="mt-5"
        items={[
          {
            label: "Due today",
            value: pulse.overdue > 0 ? `${tabCounts.due} · ${pulse.overdue} overdue` : tabCounts.due.toLocaleString("en-US"),
            icon: RiCalendarTodoLine,
            hint: `${TAB_DESCRIPTIONS.due} Overdue: the follow-up date has passed.`,
          },
          { label: "Reached", value: `${called.toLocaleString("en-US")} of ${leads.toLocaleString("en-US")}`, icon: RiUserReceivedLine, hint: "Contacts called at least once" },
          {
            label: "Connect rate",
            value: formatPercent(called > 0 ? connected / called : null),
            icon: RiPhoneLine,
            hint: called > 0 ? `${connected} of the ${called} contacts called picked up at least once` : "Nobody called yet",
          },
          { label: "Last call", value: pulse.lastCalledAt ? timeAgo(pulse.lastCalledAt) : "Never", icon: RiTimeLine },
        ]}
      />

      <PageTabs
        className="mt-6"
        label="Campaign contacts"
        value={tab}
        onChange={setTab}
        tabs={TABS.map((key) => ({ value: key, label: TAB_LABELS[key], icon: TAB_ICONS[key], count: tabCounts[key] }))}
      />

      <Frame role="tabpanel" aria-label={TAB_LABELS[tab]} className="mt-5">
        <FrameHeader
          title={TAB_LABELS[tab]}
          description={TAB_DESCRIPTIONS[tab]}
          actions={
            total > 0 && (
              <Input.Root size="small" className="w-48 sm:w-56">
                <Input.Wrapper>
                  <Input.Icon as={RiSearchLine} />
                  <Input.Input type="search" aria-label="Search contacts" placeholder="Search contacts…" value={search} onChange={(event) => setSearch(event.target.value)} />
                </Input.Wrapper>
              </Input.Root>
            )
          }
        />
        <FramePanel aria-busy={refreshing || undefined} className={cn("overflow-x-auto p-2 transition-opacity sm:p-2", refreshing && "opacity-60")}>
          {visibleContacts.length ? (
            <Table.Root className="min-w-[1060px]">
              <Table.Header>
                <Table.Row>
                  <Table.Head scope="col" className="px-4">Person</Table.Head>
                  <Table.Head scope="col" className="w-44 px-4">Company</Table.Head>
                  <Table.Head scope="col" className="w-48 px-4">Call status</Table.Head>
                  <Table.Head scope="col" className="w-56 px-4">Lead status</Table.Head>
                  <Table.Head scope="col" className="w-52 px-4">Last call</Table.Head>
                  <Table.Head scope="col" className="w-32 px-4"><span className="sr-only">Actions</span></Table.Head>
                </Table.Row>
              </Table.Header>
              <Table.Body spacing={4}>
                {visibleContacts.map((contact) => (
                  <ContactRow
                    key={contact.id}
                    contact={contact}
                    categories={categories}
                    now={now}
                    onUpdated={replaceContact}
                    onOpen={() => setOpenContactId(contact.id)}
                    onEdit={() => setEditingContact(contact)}
                    onRemove={() => setRemovingContact(contact)}
                    onCallStarted={() => {
                      setOpenContactId(contact.id);
                      void reload();
                    }}
                  />
                ))}
              </Table.Body>
            </Table.Root>
          ) : total === 0 ? (
            <EmptyState
              icon={RiTeamLine}
              title="No contacts yet"
              description="Add people one at a time, or upload a CSV or Excel file of the list to call."
              action={<div className="flex flex-wrap justify-center gap-2">{uploadButton}{addButton}</div>}
            />
          ) : inCurrentTab.length > 0 ? (
            <EmptyState
              icon={RiSearchLine}
              title="No contacts match"
              description={`Nobody in ${TAB_LABELS[tab]} matches “${search.trim()}”.`}
              action={<Button.Root variant="neutral" mode="stroke" size="xsmall" onClick={() => setSearch("")}>Clear search</Button.Root>}
            />
          ) : (
            <EmptyState
              icon={TAB_ICONS[tab]}
              title={tab === "due" ? "Nobody is due today" : tab === "follow_up" ? "No follow-ups pending" : "Nobody is done yet"}
              description={tab === "due" ? "Leads to call today and follow-ups that have come due show up here." : tab === "follow_up" ? "People you spoke to with a next step pending show up here." : "Leads move here once there is nothing left to do."}
            />
          )}
        </FramePanel>
      </Frame>

      <AddContactModal
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdded={() => { setAddOpen(false); void reload(); }}
        campaignId={campaignId}
      />
      <UploadContactsModal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onImported={() => void reload()}
        campaignId={campaignId}
      />
      <EditCampaignModal
        open={editOpen}
        onOpenChange={setEditOpen}
        campaign={campaign}
        onUpdated={(updated) => { setEditOpen(false); setCampaign(updated); }}
      />
      <DeleteCampaignModal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        campaign={campaign}
        onDeleted={() => { setDeleteOpen(false); router.push("/calling/campaigns"); }}
      />
      {/* Row modals live here, outside the table: a portal still bubbles React events to its parent row. */}
      {editingContact && (
        <EditContactModal
          open
          onOpenChange={(open) => { if (!open) setEditingContact(null); }}
          contact={editingContact}
          onSaved={() => { setEditingContact(null); void reload(); }}
          onContactChanged={(updated) => { replaceContact(updated); setEditingContact(updated); }}
        />
      )}
      {removingContact && (
        <RemoveContactModal
          open
          onOpenChange={(open) => { if (!open) setRemovingContact(null); }}
          contact={removingContact}
          onRemoved={() => { setRemovingContact(null); void reload(); }}
        />
      )}

      {openContactId && (
        <ContactPanel
          contactId={openContactId}
          onClose={() => setOpenContactId(null)}
          onChanged={() => void reload()}
        />
      )}
    </div>
  );
}

/** The last call's recording and transcript, spelled out rather than bare icons. */
function LastCallArtifacts({ call }: { call: CampaignContact["lastCall"] }) {
  if (!call) return null;
  const transcript =
    call.transcriptStatus === "pending" ? { icon: RiLoader4Line, label: "Transcribing", className: "text-text-sub-600", spin: true }
    : call.transcriptStatus === "done" ? { icon: RiFileTextLine, label: "Transcript", className: "text-success-base", spin: false }
    : call.transcriptStatus === "failed" ? { icon: RiFileTextLine, label: "Transcript failed", className: "text-error-base", spin: false }
    : null;
  if (!call.hasRecording && !transcript) return null;
  return (
    <p className="mt-0.5 flex items-center gap-2 whitespace-nowrap text-paragraph-xs text-text-sub-600">
      {call.hasRecording && (
        <span className="inline-flex items-center gap-1">
          <RiMicLine className="size-3.5" aria-hidden="true" />Recording
        </span>
      )}
      {transcript && (
        <span className={cn("inline-flex items-center gap-1", transcript.className)}>
          <transcript.icon className={cn("size-3.5", transcript.spin && "animate-spin")} aria-hidden="true" />
          {transcript.label}
        </span>
      )}
    </p>
  );
}

function ContactRow({
  contact,
  categories,
  now,
  onUpdated,
  onOpen,
  onEdit,
  onRemove,
  onCallStarted,
}: {
  contact: CampaignContact;
  categories: Record<string, unknown>[];
  now: Date;
  onUpdated: (contact: CampaignContact) => void;
  onOpen: () => void;
  onEdit: () => void;
  onRemove: () => void;
  onCallStarted: () => void;
}) {
  const person = contact.person;
  const name = person.fullName || person.firstName || "Unnamed contact";
  const domain = person.companyWebsite ? bareDomain(person.companyWebsite) : "";
  const hint = attemptHint(contact);
  const followUp = followUpHint(contact, now);
  const subtitle = titleAtCompany(person);

  return (
    <Table.Row
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => { if (event.target === event.currentTarget && event.key === "Enter") onOpen(); }}
      aria-label={`Open ${name}`}
      className="cursor-pointer outline-none focus-visible:[&>td]:bg-bg-weak-50"
    >
      <Table.Cell className="h-16 px-4">
        <div className="flex min-w-0 max-w-80 items-center gap-3">
          <Avatar name={name} src={person.profilePictureUrl} className="size-9" />
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-1.5">
              <p className="truncate text-label-sm text-text-strong-950" title={name}>{name}</p>
              {person.linkedinUrl && (
                <a
                  href={person.linkedinUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(event) => event.stopPropagation()}
                  onKeyDown={(event) => event.stopPropagation()}
                  title="LinkedIn profile"
                  aria-label={`${name} on LinkedIn`}
                  className="shrink-0 text-text-soft-400 transition hover:text-text-strong-950"
                >
                  <RiLinkedinBoxFill className="size-4" aria-hidden="true" />
                </a>
              )}
            </div>
            <p className="truncate text-paragraph-xs text-text-sub-600" title={subtitle ?? undefined}>{subtitle || person.phone || "No details"}</p>
          </div>
        </div>
      </Table.Cell>
      <Table.Cell className="px-4">
        {domain ? (
          <a
            href={`https://${domain}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
            title={person.companyName ?? domain}
            className="flex min-w-0 max-w-40 items-center gap-2 text-paragraph-sm text-text-strong-950 hover:underline"
          >
            <CompanyFavicon domain={domain} className="size-4" />
            <span className="truncate">{domain}</span>
          </a>
        ) : (
          <span className="block max-w-40 truncate text-paragraph-sm text-text-sub-600" title={person.companyName ?? undefined}>{person.companyName || "—"}</span>
        )}
      </Table.Cell>
      <Table.Cell className="px-4">
        <div className="flex flex-col items-start gap-1">
          <CallStatusBadge status={contact.callStatus} />
          {(hint || followUp) && (
            <span className="whitespace-nowrap text-paragraph-xs text-text-sub-600">
              {hint && hint.charAt(0).toUpperCase() + hint.slice(1)}
              {hint && followUp && " · "}
              {followUp && <span className={cn(followUp.overdue && "font-medium text-error-base")}>{followUp.text}</span>}
            </span>
          )}
        </div>
      </Table.Cell>
      <Table.Cell className="px-4" onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
        {/* Its own click target: picking a stage must not open the panel. */}
        <LeadStagePicker compact contact={contact} categories={categories} onUpdated={onUpdated} />
      </Table.Cell>
      <Table.Cell className="px-4">
        {contact.lastCalledAt ? (
          <div>
            <p className="whitespace-nowrap text-paragraph-sm text-text-strong-950">
              {timeAgo(contact.lastCalledAt)}
              <span className="text-text-sub-600"> · {contact.callCount} {contact.callCount === 1 ? "call" : "calls"}</span>
            </p>
            <LastCallArtifacts call={contact.lastCall} />
          </div>
        ) : (
          <span className="text-paragraph-sm text-text-soft-400">Not called yet</span>
        )}
      </Table.Cell>
      {/* Stops clicks bubbling to the row — including clicks inside the Call
          button's portaled dropdown/modal, since React bubbles synthetic
          events through the component tree, not the DOM a portal renders into. */}
      <Table.Cell className="px-4" onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-end gap-1">
          <CallButton personId={person.id} campaignContactId={contact.id} phone={person.phone} onCallStarted={onCallStarted} numberMenu={false} />
          <Dropdown.Root>
            <Dropdown.Trigger asChild>
              <Button.Root variant="neutral" mode="ghost" size="xxsmall" aria-label={`More actions for ${name}`}>
                <Button.Icon as={RiMoreLine} />
              </Button.Root>
            </Dropdown.Trigger>
            <Dropdown.Content align="end">
              <Dropdown.Item onSelect={onEdit}>
                <Dropdown.ItemIcon as={RiPencilLine} />
                Edit contact
              </Dropdown.Item>
              <Dropdown.Separator />
              <Dropdown.Item destructive onSelect={onRemove}>
                <Dropdown.ItemIcon as={RiDeleteBinLine} />
                Remove from campaign
              </Dropdown.Item>
            </Dropdown.Content>
          </Dropdown.Root>
        </div>
      </Table.Cell>
    </Table.Row>
  );
}

function AddContactModal({
  open,
  onOpenChange,
  onAdded,
  campaignId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdded: () => void;
  campaignId: string;
}) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyWebsite, setCompanyWebsite] = useState("");
  const [title, setTitle] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setFullName(""); setPhone(""); setCompanyName(""); setCompanyWebsite(""); setTitle(""); setEmail("");
      setError(""); setSubmitting(false);
    }
  }, [open]);

  const submit = async () => {
    if (!fullName.trim() || !phone.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await addCampaignContact(campaignId, {
        fullName: fullName.trim(),
        phone: phone.trim(),
        companyName: companyName.trim() || null,
        companyWebsite: companyWebsite.trim() || null,
        title: title.trim() || null,
        email: email.trim() || null,
      });
      onAdded();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal.Root open={open} onOpenChange={(next) => { if (!submitting) onOpenChange(next); }}>
      <Modal.Content>
        <Modal.Header icon={RiAddLine}>
          <Modal.Title>Add a contact</Modal.Title>
          <Modal.Description>Added to the campaign, ready to call.</Modal.Description>
        </Modal.Header>
        <Modal.Body className="space-y-3">
          {error && <FormError>{error}</FormError>}
          <TextField label="Full name" autoFocus value={fullName} onChange={setFullName} placeholder="Priya Nair" disabled={submitting} />
          <TextField label="WhatsApp number" value={phone} onChange={setPhone} placeholder="+91 98765 43210" disabled={submitting} />
          <div className="grid gap-3 sm:grid-cols-2">
            <CompanyNameField
              label="Company name (optional)"
              value={companyName}
              onChange={setCompanyName}
              onPick={(company) => { setCompanyName(company.name ?? companyName); setCompanyWebsite(company.domain); }}
              disabled={submitting}
            />
            <TextField label="Company website (optional)" value={companyWebsite} onChange={setCompanyWebsite} placeholder="acme.com" disabled={submitting} />
          </div>
          <TextField label="Title (optional)" value={title} onChange={setTitle} disabled={submitting} />
          <TextField label="Email (optional)" value={email} onChange={setEmail} disabled={submitting} />
        </Modal.Body>
        <Modal.Footer>
          <Modal.Close asChild>
            <Button.Root variant="neutral" mode="stroke" size="small" disabled={submitting}>Cancel</Button.Root>
          </Modal.Close>
          <Button.Root variant="primary" mode="filled" size="small" disabled={submitting || !fullName.trim() || !phone.trim()} onClick={() => void submit()}>
            {submitting ? "Adding…" : "Add contact"}
          </Button.Root>
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}

function UploadContactsModal({
  open,
  onOpenChange,
  onImported,
  campaignId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
  campaignId: string;
}) {
  const [fileName, setFileName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ added: number; alreadyInCampaign: number; skipped: string[] } | null>(null);

  useEffect(() => {
    if (open) {
      setFileName(""); setFile(null); setError(""); setResult(null); setSubmitting(false);
    }
  }, [open]);

  const submit = async () => {
    if (!file) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await importCampaignContacts(campaignId, file);
      setResult(response);
      onImported();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal.Root open={open} onOpenChange={(next) => { if (!submitting) onOpenChange(next); }}>
      <Modal.Content>
        <Modal.Header icon={RiUpload2Line}>
          <Modal.Title>Upload contacts</Modal.Title>
          <Modal.Description>CSV or Excel. Expected columns: Name (or First Name / Last Name), Phone (or Mobile / WhatsApp), Company, Title, Email.</Modal.Description>
        </Modal.Header>
        <Modal.Body className="space-y-3">
          {error && <FormError>{error}</FormError>}
          {!result ? (
            <label className="flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-stroke-sub-300 bg-bg-weak-50 px-4 py-8 text-center transition hover:border-primary-base focus-within:ring-2 focus-within:ring-primary-base">
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                className="sr-only"
                onChange={(event) => {
                  const chosen = event.target.files?.[0] ?? null;
                  setFile(chosen);
                  setFileName(chosen?.name ?? "");
                }}
                disabled={submitting}
              />
              <span className="mb-2 flex size-10 items-center justify-center rounded-xl bg-bg-white-0 ring-1 ring-inset ring-stroke-soft-200">
                <RiUpload2Line className="size-5 text-text-sub-600" aria-hidden="true" />
              </span>
              <span className="text-label-sm text-text-strong-950">{fileName || "Choose a .csv or .xlsx file"}</span>
              {!fileName && <span className="mt-0.5 text-paragraph-xs text-text-sub-600">Click to browse</span>}
            </label>
          ) : (
            <div className="space-y-2 rounded-xl bg-bg-weak-50 p-3 text-paragraph-sm text-text-sub-600 ring-1 ring-inset ring-stroke-soft-200">
              <p>
                <span className="font-medium tabular-nums text-text-strong-950">{result.added}</span> added ·{" "}
                <span className="font-medium tabular-nums text-text-strong-950">{result.alreadyInCampaign}</span> already in campaign ·{" "}
                <span className="font-medium tabular-nums text-text-strong-950">{result.skipped.length}</span> skipped
              </p>
              {result.skipped.length > 0 && (
                <ul className="max-h-40 space-y-1 overflow-y-auto text-paragraph-xs text-error-dark">
                  {result.skipped.map((reason, index) => <li key={index}>{reason}</li>)}
                </ul>
              )}
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          {result ? (
            <Button.Root variant="primary" mode="filled" size="small" onClick={() => onOpenChange(false)}>Done</Button.Root>
          ) : (
            <>
              <Modal.Close asChild>
                <Button.Root variant="neutral" mode="stroke" size="small" disabled={submitting}>Cancel</Button.Root>
              </Modal.Close>
              <Button.Root variant="primary" mode="filled" size="small" disabled={submitting || !file} onClick={() => void submit()}>
                {submitting ? "Uploading…" : "Upload"}
              </Button.Root>
            </>
          )}
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}
