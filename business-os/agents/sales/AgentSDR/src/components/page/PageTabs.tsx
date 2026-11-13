"use client";

import type { ComponentType } from "react";
import { cn } from "@/utils/cn";

/**
 * Underline tabs, as on Analytics: an optional icon, the label, an optional
 * count pill, and a primary bar under the active tab. `trailing` sits at the
 * right end of the row (an "Updated" note, a search box).
 */
export type PageTab<T extends string> = {
  value: T;
  label: string;
  icon?: ComponentType<{ className?: string }>;
  count?: number;
};

export function PageTabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  trailing,
  className,
}: {
  tabs: ReadonlyArray<PageTab<T>>;
  value: T;
  onChange: (value: T) => void;
  /** Names the tab list for screen readers. */
  label: string;
  trailing?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-stroke-soft-200", className)}>
      <div role="tablist" aria-label={label} className="-mb-px flex gap-5 overflow-x-auto">
        {tabs.map((tab) => {
          const active = tab.value === value;
          const Icon = tab.icon;
          return (
            <button
              key={tab.value}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => onChange(tab.value)}
              className={cn("relative flex h-10 shrink-0 items-center gap-2 text-label-sm outline-none transition-colors focus-visible:text-text-strong-950", active ? "text-text-strong-950" : "text-text-sub-600 hover:text-text-strong-950")}
            >
              {Icon && <Icon className={cn("size-[18px] shrink-0", active ? "text-text-strong-950" : "text-text-soft-400")} />}
              {tab.label}
              {tab.count !== undefined && (
                <span className={cn("rounded-md px-1.5 py-0.5 text-label-xs tabular-nums", active ? "bg-bg-strong-950 text-text-white-0" : "bg-bg-weak-50 text-text-sub-600")}>
                  {tab.count.toLocaleString("en-US")}
                </span>
              )}
              <span className={cn("absolute inset-x-0 bottom-0 h-0.5 rounded-full", active ? "bg-primary-base" : "bg-transparent")} />
            </button>
          );
        })}
      </div>
      {trailing && <div className="flex items-center gap-2 pb-2">{trailing}</div>}
    </div>
  );
}
