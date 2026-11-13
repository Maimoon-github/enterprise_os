/**
 * The sending guardrails' arithmetic — pure, so the rules are unit-tested
 * apart from the database. send.ts reads the inputs (the account's
 * connected_at, its last AgentSDR send, its new chats in the last day) inside
 * a per-account lock and asks these functions whether to send.
 *
 * "Per day" is a rolling 24 hours, not a calendar day: it needs no time zone
 * and cannot be gamed by sending 25 at 23:59 and 25 more at 00:01.
 */

export type WhatsappGuardrails = {
  warmUpHours: number;
  newChatsPerDay: number;
  minSecondsBetweenSends: number;
};

export const NEW_CHAT_WINDOW_MS = 24 * 60 * 60 * 1000;

/** The organization's WhatsApp sending rules (Settings → WhatsApp → Sending rules). */
export type WhatsappRules = { warmupHours: number; newChatsPerDay: number; secondsBetweenSends: number };

/**
 * The guardrails for one number: the organization's rules, with the
 * number's own new-chats-per-day when it has one.
 */
export function whatsappGuardrails(rules: WhatsappRules, account?: { newChatsPerDay?: number | null }): WhatsappGuardrails {
  return {
    warmUpHours: rules.warmupHours,
    newChatsPerDay: account?.newChatsPerDay ?? rules.newChatsPerDay,
    minSecondsBetweenSends: rules.secondsBetweenSends,
  };
}

/** When the new-chat warm-up ends; null when it is already over (or never started). */
export function warmUpEndsAt(connectedAt: Date | null, now: Date, warmUpHours: number): Date | null {
  if (!connectedAt) return null;
  const ends = new Date(connectedAt.getTime() + warmUpHours * 60 * 60 * 1000);
  return ends > now ? ends : null;
}

/** Whole seconds to wait before this account may send again; 0 when it may send now. */
export function secondsUntilNextSend(lastSentAt: Date | null, now: Date, minSeconds: number): number {
  if (!lastSentAt || minSeconds <= 0) return 0;
  const waitMs = lastSentAt.getTime() + minSeconds * 1000 - now.getTime();
  return waitMs > 0 ? Math.ceil(waitMs / 1000) : 0;
}

export type NewChatRefusalReason = "warm_up" | "new_chat_limit";

/**
 * Why a new chat (a number this account has never messaged) may not start
 * now, with a machine-readable reason, or null when it may. `connectedAt`
 * null means AgentSDR never saw the account connected, so its warm-up has
 * not begun.
 */
export function newChatRefusalDetail(input: {
  connectedAt: Date | null;
  newChatsInWindow: number;
  now: Date;
  guardrails: WhatsappGuardrails;
}): { reason: NewChatRefusalReason; message: string } | null {
  const { connectedAt, newChatsInWindow, now, guardrails } = input;
  if (!connectedAt && guardrails.warmUpHours > 0) {
    return { reason: "warm_up", message: "This WhatsApp number has not been seen connected yet, so it cannot start new chats. Sync the accounts and try again." };
  }
  const ends = warmUpEndsAt(connectedAt, now, guardrails.warmUpHours);
  if (ends) {
    return { reason: "warm_up", message: `This WhatsApp number was linked recently and cannot start new chats until ${ends.toISOString()} (a ${guardrails.warmUpHours}-hour warm-up). Existing chats can be answered.` };
  }
  if (newChatsInWindow >= guardrails.newChatsPerDay) {
    return { reason: "new_chat_limit", message: `This WhatsApp number has started ${newChatsInWindow} new chats in the last 24 hours, the daily limit (${guardrails.newChatsPerDay}). Existing chats can be answered.` };
  }
  return null;
}

/** Why a new chat may not start now, or null when it may. */
export function newChatRefusal(input: Parameters<typeof newChatRefusalDetail>[0]): string | null {
  return newChatRefusalDetail(input)?.message ?? null;
}
