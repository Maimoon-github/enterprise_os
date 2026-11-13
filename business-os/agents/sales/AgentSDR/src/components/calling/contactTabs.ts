import type { CampaignContact } from "@/lib/calls/contract";

/**
 * All leads, then the working views: due today (to call now, whatever the
 * reason), Follow-up (spoke to them; next steps pending) and Done. Leads
 * waiting for a later retry are under All only.
 */
export type ContactTab = "all" | "due" | "follow_up" | "done";

export const CONTACT_TABS: readonly ContactTab[] = ["all", "due", "follow_up", "done"];

/** A `?tab=` value from the URL, if it names a real tab. */
export function isContactTab(value: unknown): value is ContactTab {
  return typeof value === "string" && (CONTACT_TABS as readonly string[]).includes(value);
}

export function endOfToday(now = new Date()): Date {
  const end = new Date(now);
  end.setHours(23, 59, 59, 999);
  return end;
}

/**
 * Not done, and either its follow-up date is today or earlier, or it is to be
 * called with no date at all — never called yet, or a call that failed.
 */
export function isDueToday(contact: CampaignContact, now = new Date()): boolean {
  if (contact.stage === "done") return false;
  if (contact.followUpAt) return new Date(contact.followUpAt).getTime() <= endOfToday(now).getTime();
  return contact.stage === "to_call";
}

export function inTab(contact: CampaignContact, tab: ContactTab, now = new Date()): boolean {
  if (tab === "all") return true;
  return tab === "due" ? isDueToday(contact, now) : contact.stage === tab;
}

export function isOverdue(followUpAt: string | null, now = new Date()): boolean {
  return followUpAt !== null && new Date(followUpAt).getTime() < now.getTime();
}
