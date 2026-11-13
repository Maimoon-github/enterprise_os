export type InboxSectionKey = "inbox" | "sent" | "replied" | "scheduled" | "important" | "outOfOffice" | "pendingApproval";

export const INBOX_SECTIONS: { key: InboxSectionKey; label: string; parent?: InboxSectionKey }[] = [
  { key: "inbox", label: "Inbox" },
  { key: "replied", label: "Replied", parent: "inbox" },
  { key: "outOfOffice", label: "Out of office", parent: "inbox" },
  { key: "pendingApproval", label: "Pending approval" },
  { key: "sent", label: "Sent" },
  { key: "important", label: "Important" },
  { key: "scheduled", label: "Scheduled" },
];

/** What each folder's count means, for its tooltip. `/api/outreach/inbox/counts` only reports these three. */
export const SECTION_COUNT_HINT: Partial<Record<InboxSectionKey, string>> = {
  inbox: "unread",
  important: "starred",
  scheduled: "waiting to send",
};
