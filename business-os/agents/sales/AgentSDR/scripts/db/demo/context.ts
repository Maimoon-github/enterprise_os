/**
 * What every part of the demo seed shares: a seeded random source (the same
 * seed always builds the same world), the clock everything is placed
 * against, the people and companies created by core.ts, and the replies the
 * channel modules hand to crm.ts.
 *
 * Time: `ctx.now` is the moment the seed runs. Every timestamp is placed
 * relative to it (days ago, in business hours), never at a fixed date, and
 * src/lib/demo/clock.ts moves them all forward each day after that, so the
 * demo always looks current.
 */

import type { CompanySeed, ReplyIntent, TeamKey } from "./content";
import { REPLIES } from "./content";

export const SEED_SOURCE = "demo-seed";

export type Channel = "email" | "linkedin" | "whatsapp";

export type DemoCompany = CompanySeed & { id: string; domain: string };

export type DemoPerson = {
  id: string;
  firstName: string;
  lastName: string;
  fullName: string;
  gender: "female" | "male";
  email: string;
  /** Bare LinkedIn slug, as people.linkedin_url stores it. */
  linkedinSlug: string;
  /** E.164; only people in the WhatsApp pool have one. */
  phone: string | null;
  title: string;
  seniority: string;
  location: string;
  /** A stable public portrait, or null (initials are shown). */
  avatarUrl: string | null;
  company: DemoCompany;
};

/**
 * A reply a channel module ingested. crm.ts classifies it into `intent`'s
 * subcategory, moves some records further along the pipeline, and writes
 * drafts — all at times derived from `sentAt`.
 */
export type DemoReply = {
  recordId: string;
  personId: string;
  conversationId: string;
  /** The inbound crm_conversation_messages row. */
  messageId: string;
  channel: Channel;
  intent: ReplyIntent;
  sentAt: Date;
  /** The rep who owns the conversation (drafts are signed by them). */
  rep: TeamKey;
};

export type DemoContext = {
  organizationId: string;
  now: Date;
  rand: Rng;
  users: Record<TeamKey, { id: string; name: string; email: string }>;
  companies: DemoCompany[];
  people: DemoPerson[];
  /**
   * Disjoint slices of `people` per channel, so each person's story is told
   * once. WhatsApp people have phone numbers; most LinkedIn people have photos.
   */
  pools: { email: DemoPerson[]; linkedin: DemoPerson[]; whatsapp: DemoPerson[]; unassigned: DemoPerson[] };
  pipelineId: string;
  replies: DemoReply[];
  summary: Record<string, number>;
};

// ---------------------------------------------------------------------------
// Randomness — mulberry32, so a run is reproducible.
// ---------------------------------------------------------------------------

export type Rng = {
  next(): number;
  int(min: number, max: number): number;
  chance(p: number): boolean;
  pick<T>(items: readonly T[]): T;
  weighted<T>(items: readonly (readonly [T, number])[]): T;
  shuffle<T>(items: readonly T[]): T[];
};

export function createRng(seed: number): Rng {
  let a = seed >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const rng: Rng = {
    next,
    int: (min, max) => min + Math.floor(next() * (max - min + 1)),
    chance: (p) => next() < p,
    pick: (items) => items[Math.floor(next() * items.length)],
    weighted: (items) => {
      const total = items.reduce((sum, [, w]) => sum + w, 0);
      let roll = next() * total;
      for (const [item, w] of items) {
        roll -= w;
        if (roll < 0) return item;
      }
      return items[items.length - 1][0];
    },
    shuffle: (items) => {
      const out = [...items];
      for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
      }
      return out;
    },
  };
  return rng;
}

// ---------------------------------------------------------------------------
// Time
// ---------------------------------------------------------------------------

export const MINUTE = 60_000;
export const HOUR = 60 * MINUTE;
export const DAY = 24 * HOUR;

export const addMs = (d: Date, ms: number) => new Date(d.getTime() + ms);

/** `days` before ctx.now, at the same clock time. */
export const daysAgo = (ctx: DemoContext, days: number) => new Date(ctx.now.getTime() - days * DAY);

/**
 * A plausible working-hours moment `days` before now: a weekday (weekends roll
 * back to Friday), between 08:30 and 17:30 UTC-ish, with jitter. Never in the
 * future — today's slot is clamped to before now.
 */
export function workTime(ctx: DemoContext, days: number): Date {
  const d = daysAgo(ctx, days);
  const dow = d.getUTCDay();
  if (dow === 0) d.setUTCDate(d.getUTCDate() - 2);
  if (dow === 6) d.setUTCDate(d.getUTCDate() - 1);
  d.setUTCHours(ctx.rand.int(13, 21), ctx.rand.int(0, 59), ctx.rand.int(0, 59), 0);
  if (d.getTime() > ctx.now.getTime()) return new Date(ctx.now.getTime() - ctx.rand.int(10, 180) * MINUTE);
  return d;
}

/** A moment shortly after `from` (a reply, an answer): minutes to a day or two later, capped at now. */
export function after(ctx: DemoContext, from: Date, minMinutes: number, maxMinutes: number): Date {
  const t = from.getTime() + ctx.rand.int(minMinutes, maxMinutes) * MINUTE;
  return new Date(Math.min(t, ctx.now.getTime() - ctx.rand.int(2, 30) * MINUTE));
}

// ---------------------------------------------------------------------------
// Words
// ---------------------------------------------------------------------------

/** A reply in `intent`'s voice, filled in for this lead and rep. */
export function replyText(
  ctx: DemoContext,
  intent: ReplyIntent,
  style: "long" | "short",
  person: DemoPerson,
  repFirst: string,
): string {
  const options = REPLIES[intent][style].length ? REPLIES[intent][style] : REPLIES[intent].long;
  const text = ctx.rand
    .pick(options)
    .replaceAll("{first}", repFirst)
    .replaceAll("{company}", person.company.name)
    .replaceAll("{domain}", person.company.domain)
    .replaceAll("{industry}", person.company.industry)
    .replaceAll("{product}", "Northwind Signal");
  // Emails get the lead's sign-off; chat messages do not.
  return style === "long" && !/out of (the )?office|parental leave|moved on|remove me/i.test(text)
    ? `${text}\n${person.firstName}`
    : text;
}

export function count(ctx: DemoContext, label: string, n: number) {
  ctx.summary[label] = (ctx.summary[label] ?? 0) + n;
}
