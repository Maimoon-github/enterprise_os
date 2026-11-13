"use client";

import type { ReactNode } from "react";
import { RiArrowLeftSLine, RiArrowRightSLine, RiSearchLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import * as SegmentedControl from "@/components/alignui/segmented-control";
import { Frame, FramePanel } from "@/components/analytics/kit/Frame";
import { EmptyState } from "@/components/page/EmptyState";
import { cn } from "@/utils/cn";

/**
 * The shared shape of the Connected accounts sections (email, LinkedIn,
 * WhatsApp): a KPI strip, then one Frame holding the account table with a
 * status filter and a search in its header. Keep the three alike by building
 * them from these.
 */

/** The health filter every account list offers. */
export type AccountFilter = "all" | "healthy" | "attention";

export const ACCOUNT_FILTER_LABEL: Record<AccountFilter, string> = {
  all: "All",
  healthy: "Healthy",
  attention: "Needs attention",
};

export function AccountsFrame({
  title,
  description,
  filter,
  onFilterChange,
  counts,
  search,
  onSearchChange,
  searchPlaceholder,
  footer,
  children,
}: {
  title: string;
  description: ReactNode;
  filter: AccountFilter;
  onFilterChange: (filter: AccountFilter) => void;
  counts: Record<AccountFilter, number>;
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder: string;
  /** Under the panel, inside the frame: a pager. */
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Frame className="mt-5">
      <header className="flex flex-col gap-3 px-4 pb-3 pt-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 lg:flex-1">
          <h3 className="text-label-sm text-text-strong-950">{title}</h3>
          <p className="mt-0.5 text-paragraph-xs text-text-sub-600">{description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:shrink-0 lg:flex-nowrap">
          <SegmentedControl.Root value={filter} onValueChange={(value) => onFilterChange(value as AccountFilter)}>
            <SegmentedControl.List className="w-auto auto-cols-auto">
              {(Object.keys(ACCOUNT_FILTER_LABEL) as AccountFilter[]).map((key) => (
                <SegmentedControl.Trigger key={key} value={key} className="gap-1.5 px-2.5 sm:px-3">
                  {ACCOUNT_FILTER_LABEL[key]}
                  <span className="tabular-nums text-text-soft-400">{counts[key]}</span>
                </SegmentedControl.Trigger>
              ))}
            </SegmentedControl.List>
          </SegmentedControl.Root>
          <Input.Root size="small" className="w-full sm:w-48">
            <Input.Wrapper>
              <Input.Icon as={RiSearchLine} />
              <Input.Input
                type="search"
                aria-label={searchPlaceholder}
                placeholder={searchPlaceholder}
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
              />
            </Input.Wrapper>
          </Input.Root>
        </div>
      </header>
      <FramePanel className="overflow-x-auto p-2 sm:p-2">{children}</FramePanel>
      {footer}
    </Frame>
  );
}

/** In place of the table when the filter or search matches nothing. */
export function AccountsNoMatch({ noun }: { noun: string }) {
  return (
    <EmptyState
      compact
      icon={RiSearchLine}
      title={`No ${noun} match`}
      description="Try another filter, or clear the search."
    />
  );
}

/** The first cell of an account row: picture or mark, a name and one muted line. */
export function AccountIdentity({
  media,
  name,
  detail,
  extra,
  className,
}: {
  media: ReactNode;
  name: ReactNode;
  detail?: ReactNode;
  extra?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center gap-3", className)}>
      <div className="relative shrink-0">{media}</div>
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-1.5">{name}</div>
        {detail && <p className="truncate text-paragraph-xs text-text-sub-600">{detail}</p>}
        {extra}
      </div>
    </div>
  );
}

/** A dot on the corner of an avatar: green when the account can send, red when it cannot. */
export function PresenceDot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full ring-2 ring-bg-white-0",
        ok ? "bg-success-base" : "bg-error-base",
      )}
    />
  );
}

/** Page size for long account lists. */
export const ACCOUNTS_PAGE_SIZE = 25;

/** "1–25 of 105" with previous / next, shown only when there is more than one page. */
export function AccountsPager({
  page,
  total,
  pageSize = ACCOUNTS_PAGE_SIZE,
  noun,
  onPage,
}: {
  page: number;
  total: number;
  pageSize?: number;
  noun: string;
  onPage: (page: number) => void;
}) {
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  const from = page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);
  return (
    <div className="flex items-center justify-between gap-3 px-4 pb-1.5 pt-2">
      <p className="text-paragraph-xs tabular-nums text-text-sub-600">
        {from}–{to} of {total} {noun}
      </p>
      <div className="flex items-center gap-1.5">
        <Button.Root variant="neutral" mode="stroke" size="xxsmall" disabled={page === 0} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <Button.Icon as={RiArrowLeftSLine} />
        </Button.Root>
        <span className="text-paragraph-xs tabular-nums text-text-sub-600">
          {page + 1} / {pages}
        </span>
        <Button.Root variant="neutral" mode="stroke" size="xxsmall" disabled={page >= pages - 1} onClick={() => onPage(page + 1)} aria-label="Next page">
          <Button.Icon as={RiArrowRightSLine} />
        </Button.Root>
      </div>
    </div>
  );
}
