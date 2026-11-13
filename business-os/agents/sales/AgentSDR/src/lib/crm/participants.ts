import { recipientsFromRaw } from "@/lib/email/recipients";
import type { MessageParticipants } from "./ai/types";

/**
 * Who an email message was between, for the AI context. Inbound `raw` is the
 * parsed message (`fromEmail`, `to`, `cc`); outbound `raw` carries `to`/`cc` as
 * sent and the sender is the conversation's mailbox. Bcc is never exposed to
 * the model. Returns undefined for non-email messages or when nothing is known.
 */
export function messageParticipants(message: {
  channel: string;
  direction: "inbound" | "outbound";
  accountRef: string;
  raw: unknown;
}): MessageParticipants | undefined {
  if (message.channel !== "email") return undefined;
  const r = message.raw && typeof message.raw === "object" && !Array.isArray(message.raw)
    ? (message.raw as Record<string, unknown>)
    : {};
  const { to, cc } = recipientsFromRaw(message.raw);
  const from = message.direction === "outbound"
    ? message.accountRef
    : typeof r.fromEmail === "string" && r.fromEmail.trim() ? r.fromEmail.trim().toLowerCase() : null;
  if (!from && to.length === 0 && cc.length === 0) return undefined;
  return { from, to: to.map((a) => a.email), cc: cc.map((a) => a.email) };
}
