import type { ComponentType } from "react";

/**
 * A slim row of live figures ("today", "next send") for a detail page's
 * header — lighter than a KpiStrip, so it doesn't compete with the headline
 * numbers below it. Two per row on mobile, all in one row from `lg`.
 */
export type StatRowItem = {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
  /** Tooltip-free explanation, shown as the element's title. */
  hint?: string;
};

export function StatRow({ items, className = "" }: { items: StatRowItem[]; className?: string }) {
  return (
    <dl className={`grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-stroke-soft-200 ring-1 ring-inset ring-stroke-soft-200 lg:grid-flow-col lg:grid-cols-none lg:auto-cols-fr ${className}`}>
      {items.map(({ label, value, icon: Icon, hint }) => (
        <div key={label} title={hint} className="flex min-w-0 items-center gap-3 bg-bg-white-0 px-4 py-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-bg-weak-50 ring-1 ring-inset ring-stroke-soft-200">
            <Icon className="size-4 text-text-sub-600" />
          </span>
          <div className="min-w-0">
            <dt className="truncate text-paragraph-xs text-text-sub-600">{label}</dt>
            <dd className="truncate text-label-md tabular-nums text-text-strong-950">{value}</dd>
          </div>
        </div>
      ))}
    </dl>
  );
}
