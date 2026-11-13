/**
 * Body of POST /api/outreach/inbox/leads/[id]/reply, the Master Inbox's send.
 *
 * The composer posts `to`, `cc`, `bcc` and any future keys. `to` (and unknown
 * keys) are ignored rather than rejected: the server always sends to the
 * conversation's contact, so the Master Inbox cannot redirect a thread. `cc`
 * and `bcc` are honoured (reply-all); they are validated, deduplicated and
 * capped here, and the send path removes the contact and our own mailbox and
 * refuses suppressed / Do Not Contact addresses.
 */
import { CrmConfigurationValidationError, parseOptionalText, parseRequiredText, parseUuid } from "@/lib/crm/categories";
import { dedupeAddresses, isValidEmail, MAX_REPLY_EXTRA_RECIPIENTS, normalizeEmail } from "@/lib/email/recipients";

export type InboxReplyRequest = {
  subject: string;
  text: string;
  html: string | null;
  /** Extra visible recipients, lower-cased, valid, unique (bcc never repeats a cc). */
  cc: string[];
  bcc: string[];
  /** An existing awaiting-review CRM draft to edit and send instead of creating a manual one. */
  draft: { id: string; revision: number } | null;
};

export const INBOX_REPLY_SUBJECT_MAX = 998;
export const INBOX_REPLY_BODY_MAX = 100_000;

function parseAddressField(value: unknown, label: string): string[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) throw new CrmConfigurationValidationError(`${label} must be an array of email addresses`);
  const out: string[] = [];
  for (const item of value) {
    const raw = typeof item === "string"
      ? item
      : item && typeof item === "object" && typeof (item as { email?: unknown }).email === "string"
        ? (item as { email: string }).email
        : null;
    if (raw === null) throw new CrmConfigurationValidationError(`${label} must contain only email addresses`);
    const email = normalizeEmail(raw);
    if (!isValidEmail(email)) throw new CrmConfigurationValidationError(`${label} has an invalid email address: ${raw.trim().slice(0, 100)}`);
    out.push(email);
  }
  return out;
}

/** Parses optional `cc`/`bcc` (string[] or {email}[]) shared by every send body. */
export function parseExtraRecipients(cc: unknown, bcc: unknown): { cc: string[]; bcc: string[] } {
  const ccList = dedupeAddresses(parseAddressField(cc, "cc").map((email) => ({ email, name: null }))).map((a) => a.email);
  const bccList = dedupeAddresses(parseAddressField(bcc, "bcc").map((email) => ({ email, name: null })), ccList).map((a) => a.email);
  if (ccList.length + bccList.length > MAX_REPLY_EXTRA_RECIPIENTS) {
    throw new CrmConfigurationValidationError(`cc and bcc together may have at most ${MAX_REPLY_EXTRA_RECIPIENTS} addresses`);
  }
  return { cc: ccList, bcc: bccList };
}

export function parseInboxReplyRequest(value: unknown): InboxReplyRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CrmConfigurationValidationError("Request body must be a JSON object");
  }
  const body = value as Record<string, unknown>;
  const subject = parseRequiredText(body.subject, "subject", INBOX_REPLY_SUBJECT_MAX);
  const text = parseRequiredText(body.text, "text", INBOX_REPLY_BODY_MAX);
  // An empty HTML part means "text only", not a validation failure.
  const html = typeof body.html === "string" && !body.html.trim()
    ? null
    : parseOptionalText(body.html, "html", INBOX_REPLY_BODY_MAX) ?? null;

  let draft: InboxReplyRequest["draft"] = null;
  if (body.draftId !== undefined && body.draftId !== null) {
    const id = parseUuid(body.draftId, "draftId");
    const revision = body.revision;
    if (!Number.isSafeInteger(revision) || Number(revision) < 0) {
      throw new CrmConfigurationValidationError("revision must be a non-negative integer when draftId is given");
    }
    draft = { id, revision: Number(revision) };
  }
  const { cc, bcc } = parseExtraRecipients(body.cc, body.bcc);
  return { subject, text, html, cc, bcc, draft };
}
