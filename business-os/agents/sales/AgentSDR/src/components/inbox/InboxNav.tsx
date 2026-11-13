"use client";

import { TriageTabs, type TriageTab } from "./shell/InboxShell";
import { INBOX_SECTIONS, SECTION_COUNT_HINT, type InboxSectionKey } from "./inboxSections";

type Counts = Partial<Record<InboxSectionKey, number>>;

/** The folders that decide what to work on next; the rest sit under "More". */
const PRIMARY: InboxSectionKey[] = ["inbox", "replied", "pendingApproval"];

/** Shorter names for the tab bar, where space is tight. */
const TAB_LABEL: Partial<Record<InboxSectionKey, string>> = {
  replied: "Replies",
  pendingApproval: "To approve",
};

const TAB_TITLE: Partial<Record<InboxSectionKey, string>> = {
  inbox: "Every email received",
  replied: "Replies from leads, without out-of-office auto-replies",
  pendingApproval: "AI-drafted replies waiting for your review",
  outOfOffice: "Auto-replies and out-of-office notices",
  important: "Messages you starred",
  scheduled: "Queued to send",
};

function toTab(key: InboxSectionKey, counts: Counts): TriageTab {
  const section = INBOX_SECTIONS.find((s) => s.key === key)!;
  const count = counts[key];
  const hint = SECTION_COUNT_HINT[key];
  return {
    key,
    label: TAB_LABEL[key] ?? section.label,
    count: count ?? null,
    countTitle: count !== undefined ? `${count.toLocaleString("en-US")}${hint ? ` ${hint}` : ""}` : undefined,
    title: TAB_TITLE[key],
  };
}

/**
 * Master Inbox folders as the list's tab bar: Inbox, Replies and To approve
 * up front, Important, Out of office, Sent and Scheduled under "More". Counts
 * are what `/api/outreach/inbox/counts` reports (unread, starred, queued).
 */
export default function InboxFolderTabs({
  active,
  onSelect,
  counts,
}: {
  active: InboxSectionKey;
  onSelect: (key: InboxSectionKey) => void;
  counts: Counts;
}) {
  const more = INBOX_SECTIONS.map((s) => s.key).filter((key) => !PRIMARY.includes(key));
  return (
    <TriageTabs
      label="Folders"
      tabs={PRIMARY.map((key) => toTab(key, counts))}
      more={more.map((key) => toTab(key, counts))}
      value={active}
      onChange={(key) => onSelect(key as InboxSectionKey)}
    />
  );
}
