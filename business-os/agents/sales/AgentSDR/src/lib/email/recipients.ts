/**
 * Who an email was addressed to, in one shape for every place that reads it.
 *
 * Recipients are not columns: they live in the message's `raw` jsonb, on both
 * Master Inbox rows (`crm_messages.raw`) and CRM rows
 * (`crm_conversation_messages.raw`).
 *
 * - Inbound: `raw` is the parsed `InboundMessage`, which carries `to`, `cc` and
 *   `replyTo`. Rows ingested before those keys existed only have
 *   `toEmail` (the first To address) and `ccEmails`.
 * - Outbound (a rep's reply): `raw` carries `to`, `cc` and `bcc` as sent.
 *
 * Client-safe: no imports, so the inbox UI can share it.
 */

export type EmailAddress = { email: string; name: string | null };

export type MessageRecipients = {
  to: EmailAddress[];
  cc: EmailAddress[];
  bcc: EmailAddress[];
};

/** Upper bound on Cc + Bcc on one reply; a reply-all, not a mail merge. */
export const MAX_REPLY_EXTRA_RECIPIENTS = 20;

const EMAIL_PATTERN = /^[^\s@<>(),;:"[\]]+@[^\s@<>(),;:"[\]]+\.[^\s@<>(),;:"[\]]+$/;

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

export function isValidEmail(value: string): boolean {
  return value.length <= 320 && EMAIL_PATTERN.test(value);
}

function asAddressList(value: unknown): EmailAddress[] {
  if (!Array.isArray(value)) return [];
  const out: EmailAddress[] = [];
  for (const item of value) {
    if (typeof item === "string") {
      const email = normalizeEmail(item);
      if (isValidEmail(email)) out.push({ email, name: null });
    } else if (item && typeof item === "object") {
      const { email, name } = item as { email?: unknown; name?: unknown };
      if (typeof email !== "string") continue;
      const normalized = normalizeEmail(email);
      if (!isValidEmail(normalized)) continue;
      out.push({ email: normalized, name: typeof name === "string" && name.trim() ? name.trim() : null });
    }
  }
  return dedupeAddresses(out);
}

/** Keeps the first occurrence of each address, preserving order. */
export function dedupeAddresses(list: EmailAddress[], exclude: Iterable<string> = []): EmailAddress[] {
  const seen = new Set(Array.from(exclude, normalizeEmail));
  const out: EmailAddress[] = [];
  for (const address of list) {
    const email = normalizeEmail(address.email);
    if (seen.has(email)) continue;
    seen.add(email);
    out.push({ ...address, email });
  }
  return out;
}

/**
 * Reads a message's recipients from its `raw` jsonb, falling back to the
 * legacy single-address keys, then to `fallbackTo` (the row's `to_email`).
 */
export function recipientsFromRaw(raw: unknown, fallbackTo?: string | null): MessageRecipients {
  const r = raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  let to = asAddressList(r.to);
  if (to.length === 0) to = asAddressList(typeof r.toEmail === "string" ? [r.toEmail] : []);
  if (to.length === 0 && fallbackTo) to = asAddressList([fallbackTo]);
  let cc = asAddressList(r.cc);
  if (cc.length === 0) cc = asAddressList(r.ccEmails);
  return { to, cc, bcc: asAddressList(r.bcc) };
}

/**
 * The Cc for a reply-all: everyone on the message being answered except the
 * lead (who is the To) and our own mailbox — the same set Gmail's "Reply all"
 * fills in.
 */
export function replyAllCc(
  message: { fromEmail: string | null; recipients: MessageRecipients },
  exclude: { mailbox: string | null; lead: string | null },
): EmailAddress[] {
  const candidates: EmailAddress[] = [
    ...(message.fromEmail ? [{ email: message.fromEmail, name: null }] : []),
    ...message.recipients.to,
    ...message.recipients.cc,
  ];
  const skip = [exclude.mailbox, exclude.lead].filter((v): v is string => Boolean(v));
  return dedupeAddresses(candidates, skip).slice(0, MAX_REPLY_EXTRA_RECIPIENTS);
}
