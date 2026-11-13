import { and, eq } from "drizzle-orm";
import { channelRules } from "@/lib/channels/rules.server";
import { linkedInAccounts } from "@/lib/linkedin/schema";
import { mailboxes } from "@/lib/outreach/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { whatsappAccounts } from "@/lib/whatsapp/schema";
import type { DraftNow, DraftSender } from "./ai/draft";
import type { CrmExecutor } from "./repository";
import type { CrmChannel } from "./schema";

/**
 * Who a draft goes out as and when it is written — context the model had to
 * guess before: it signed as whoever the knowledge named, while the message
 * left from another teammate's mailbox or LinkedIn account, and it had no
 * "today" for "tomorrow" or "Friday".
 */

/** A name worth signing with: not a bare phone number or an email address. */
export function usableSenderName(value: string | null | undefined): string | null {
  const name = value?.replace(/\s+/g, " ").trim() ?? "";
  if (!name || name.includes("@")) return null;
  if (/^[+\d\s()-]+$/.test(name)) return null;
  return name;
}

/** "pgarg@x.com" → "Pgarg": the best a mailbox with no display name offers. */
function nameFromEmail(address: string): string | null {
  const local = address.split("@")[0]?.split(/[._+-]/)[0] ?? "";
  return local ? usableSenderName(local.charAt(0).toUpperCase() + local.slice(1)) : null;
}

export async function loadDraftSender(
  executor: CrmExecutor,
  conversation: { channel: CrmChannel; accountRef: string },
): Promise<DraftSender> {
  const { channel, accountRef } = conversation;
  if (channel === "email") {
    const [mailbox] = await executor.select({ displayName: mailboxes.displayName }).from(mailboxes)
      .where(and(inOrg(mailboxes), eq(mailboxes.emailAddress, accountRef))).limit(1);
    return { name: usableSenderName(mailbox?.displayName) ?? nameFromEmail(accountRef), account: accountRef };
  }
  if (channel === "linkedin") {
    const [account] = await executor.select({ name: linkedInAccounts.name, username: linkedInAccounts.username })
      .from(linkedInAccounts)
      .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.linkedinId, accountRef))).limit(1);
    return { name: usableSenderName(account?.name), account: account?.username ? `LinkedIn @${account.username}` : "LinkedIn" };
  }
  const [number] = await executor.select({ name: whatsappAccounts.name, phone: whatsappAccounts.phone })
    .from(whatsappAccounts)
    .where(and(inOrg(whatsappAccounts), eq(whatsappAccounts.unipileAccountId, accountRef))).limit(1);
  return { name: usableSenderName(number?.name), account: number?.phone ? `WhatsApp ${number.phone}` : "WhatsApp" };
}

/** The current moment as the model should read it: the organization's local time. */
export function draftNow(at: Date, timeZone: string): DraftNow {
  let local: string;
  try {
    local = new Intl.DateTimeFormat("en-GB", {
      timeZone, weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
    }).format(at);
  } catch {
    return draftNow(at, "UTC");
  }
  return { iso: at.toISOString(), timeZone, local };
}

/** Now, in the organization's time zone (Settings → Organization). */
export async function loadDraftNow(at: Date = new Date()): Promise<DraftNow> {
  const { timeZone } = await channelRules("general");
  return draftNow(at, timeZone);
}
