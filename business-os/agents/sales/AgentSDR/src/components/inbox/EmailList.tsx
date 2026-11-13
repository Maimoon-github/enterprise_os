"use client";

import { useMemo, useState } from "react";
import { RiArrowDownSLine, RiRobot2Line, RiStarFill } from "@remixicon/react";
import type { InboxMessageRow } from "@/lib/inbox/queries";
import { crmCategoryLabel } from "@/components/crm/InboxCrmStrip";
import { cn } from "@/utils/cn";
import {
  CategoryChip,
  ConversationRow,
  DayHeading,
  DraftChip,
  InboxAvatar,
  RowBadge,
  RowsSkeleton,
  fullTime,
  rowTime,
  withRecencyBreaks,
  type BadgeTone,
} from "./shell/InboxShell";

/** Lead status group → badge tone, for leads with no CRM record. Only outcomes wear a colour. */
const GROUP_TONE: Record<string, BadgeTone> = {
  interested: "green",
  not_interested: "red",
  wrong_poc: "orange",
};

/** A lead's name, or their address when there is none. */
export function leadDisplayName(first: string | null, last: string | null, email: string): string {
  return [first, last].filter(Boolean).join(" ").trim() || email;
}

const AUTOMATED_SENDER = /^(dmarc[\w.-]*|no-?reply[\w.-]*|do-?not-?reply|mailer-daemon|postmaster|bounces?|notifications?|reports?)@/i;
const AUTOMATED_SUBJECT = /\b(dmarc|aggregate report|report domain:|delivery status notification|undeliverable|mail delivery (failed|subsystem))\b/i;

/**
 * Machine-sent mail — DMARC aggregate reports, no-reply notifications, bounces.
 * A client-side rule on the sender and subject: the server has no such flag,
 * so folder totals and unread counts still include these.
 */
export function isAutomatedEmail(row: InboxMessageRow): boolean {
  if (row.direction !== "inbound") return false;
  const sender = row.fromEmail ?? row.leadEmail;
  return AUTOMATED_SENDER.test(sender) || AUTOMATED_SUBJECT.test(row.subject ?? "");
}

/** Groups consecutive rows sharing the same lead into a single "stack" — count reflects extra items folded in. */
function stackRows(rows: InboxMessageRow[]): { row: InboxMessageRow; stackCount: number }[] {
  const stacks: { row: InboxMessageRow; stackCount: number }[] = [];
  for (const row of rows) {
    const last = stacks[stacks.length - 1];
    if (last && last.row.leadId === row.leadId) {
      last.stackCount += 1;
    } else {
      stacks.push({ row, stackCount: 1 });
    }
  }
  return stacks;
}

function previewOf(row: InboxMessageRow): string {
  const body = (row.bodyText ?? "").replace(/\s+/g, " ").trim();
  return body || "(no content)";
}

function EmailRow({ row, stackCount, selected, onSelect }: { row: InboxMessageRow; stackCount: number; selected: boolean; onSelect: () => void }) {
  const name = leadDisplayName(row.leadFirstName, row.leadLastName, row.leadEmail);
  const isUnread = row.direction === "inbound" && !row.openedAt;
  const sentAt = row.sentAt ? new Date(row.sentAt) : null;
  const outbound = row.direction === "outbound";
  const hasDraft = row.hasDraft || row.crm?.hasDraft === true;
  const category = row.crm ? (
    <CategoryChip categoryKey={row.crm.categoryKey} label={crmCategoryLabel(row.crm)} />
  ) : row.statusLabel ? (
    <RowBadge tone={GROUP_TONE[row.statusGroup ?? ""] ?? "gray"}>{row.statusLabel}</RowBadge>
  ) : null;

  return (
    <ConversationRow
      selected={selected}
      unread={isUnread}
      onSelect={onSelect}
      avatar={<InboxAvatar name={name} />}
      title={name}
      subtitle={row.leadCompany && row.leadCompany !== name ? row.leadCompany : undefined}
      time={sentAt ? rowTime(sentAt) : "Scheduled"}
      timeTitle={fullTime(sentAt)}
      headline={
        <>
          {outbound && row.sentAt && <span className="text-text-soft-400">You: </span>}
          {row.subject?.trim() || "(no subject)"}
        </>
      }
      snippet={previewOf(row)}
      hint={row.leadMailbox ? `Mailbox: ${row.leadMailbox}` : undefined}
      meta={
        category || hasDraft || row.important || stackCount > 1 ? (
          <>
            {hasDraft && <DraftChip />}
            {category}
            <span className="flex-1" />
            {row.important && <RiStarFill className="size-3.5 shrink-0 text-warning-base" aria-label="Important" />}
            {stackCount > 1 && (
              <span className="shrink-0 text-paragraph-xs tabular-nums text-text-soft-400" title={`${stackCount} messages from this lead in a row`}>
                {stackCount} messages
              </span>
            )}
          </>
        ) : undefined
      }
    />
  );
}

/**
 * The Master Inbox list: rows grouped Today / Yesterday / This week / Earlier,
 * consecutive messages from one lead folded into one row, and — where
 * `bundleAutomated` is set — machine mail (DMARC reports, no-reply senders)
 * gathered into one collapsed "Automated" row at the top.
 */
export default function EmailList({
  rows,
  selectedId,
  onSelect,
  loading,
  suppressDateDividers = false,
  bundleAutomated = false,
}: {
  rows: InboxMessageRow[];
  selectedId: string | null;
  onSelect: (row: InboxMessageRow) => void;
  loading: boolean;
  suppressDateDividers?: boolean;
  bundleAutomated?: boolean;
}) {
  const [automatedOpen, setAutomatedOpen] = useState<boolean | null>(null);
  const { people, automated } = useMemo(() => {
    if (!bundleAutomated) return { people: rows, automated: [] as InboxMessageRow[] };
    const people: InboxMessageRow[] = [];
    const automated: InboxMessageRow[] = [];
    for (const row of rows) (isAutomatedEmail(row) ? automated : people).push(row);
    return { people, automated };
  }, [rows, bundleAutomated]);
  const stacks = useMemo(() => stackRows(people), [people]);
  const grouped = useMemo(
    () => withRecencyBreaks(stacks, (s) => (suppressDateDividers || !s.row.sentAt ? null : new Date(s.row.sentAt))),
    [stacks, suppressDateDividers],
  );
  const automatedStacks = useMemo(() => stackRows(automated), [automated]);
  const automatedUnread = automated.filter((row) => !row.openedAt).length;
  // Closed by default; open when the open thread is automated mail, so the selection stays visible.
  const bundleOpen = automatedOpen ?? automated.some((row) => row.id === selectedId);

  if (loading && rows.length === 0) return <RowsSkeleton />;

  return (
    <div>
      {automated.length > 0 && (
        <div className="pt-1.5">
          <button
            type="button"
            data-inbox-row
            onClick={() => setAutomatedOpen(!bundleOpen)}
            aria-expanded={bundleOpen}
            className="flex w-full items-center gap-3 rounded-xl py-2 pl-4 pr-3 text-left outline-none transition-colors hover:bg-bg-weak-50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-base"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-bg-weak-50 text-text-sub-600 ring-1 ring-inset ring-stroke-soft-200">
              <RiRobot2Line className="size-4" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5 text-label-sm text-text-strong-950">
                Automated
                <span className="text-paragraph-xs tabular-nums text-text-soft-400">{automated.length.toLocaleString("en-US")}</span>
              </span>
              <span className="block truncate text-paragraph-xs text-text-soft-400">
                DMARC reports, no-reply and delivery notices{automatedUnread ? ` · ${automatedUnread} unread` : ""}
              </span>
            </span>
            <RiArrowDownSLine className={cn("size-4 shrink-0 text-text-soft-400 transition-transform", bundleOpen && "rotate-180")} aria-hidden="true" />
          </button>
          {bundleOpen && (
            <div className="ml-4 border-l border-stroke-soft-200 pl-1">
              {automatedStacks.map(({ row, stackCount }) => (
                <EmailRow key={row.id} row={row} stackCount={stackCount} selected={selectedId === row.id} onSelect={() => onSelect(row)} />
              ))}
            </div>
          )}
        </div>
      )}
      {grouped.map(({ row: { row, stackCount }, heading }) => (
        <div key={row.id}>
          {heading && <DayHeading>{heading}</DayHeading>}
          <EmailRow row={row} stackCount={stackCount} selected={selectedId === row.id} onSelect={() => onSelect(row)} />
        </div>
      ))}
    </div>
  );
}
