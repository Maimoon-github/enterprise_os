"use client";

import * as Tooltip from "@/components/alignui/tooltip";
import { formatCompact, formatPercent } from "../theme";

/**
 * Part-to-whole horizontal bar: 2px gaps between segments, rounded ends, and a
 * legend underneath with label, value and share. Each segment has a hover /
 * focus tooltip. Prefer this to a donut.
 *
 * Props: `items` [{ key, label, value, color }] (zero-value items appear in
 * the legend only), `valueFormat` (default formatCompact), `hideLegend` (omit the built-in legend when the caller draws its own rows).
 */
export type SegmentItem = { key: string; label: string; value: number; color: string };

export function SegmentedBar({ items, valueFormat = formatCompact, hideLegend = false }: { items: SegmentItem[]; valueFormat?: (value: number) => string; hideLegend?: boolean }) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const share = (value: number) => (total > 0 ? value / total : null);
  return (
    <Tooltip.Provider delayDuration={0}>
      <div>
        <div role="img" aria-label={items.map((i) => `${i.label} ${valueFormat(i.value)}`).join(", ")} className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-bg-weak-50">
          {items
            .filter((item) => item.value > 0)
            .map((item) => (
              <Tooltip.Root key={item.key}>
                <Tooltip.Trigger asChild>
                  <span tabIndex={0} className="h-full min-w-1 outline-none transition-opacity first:rounded-l-full last:rounded-r-full hover:opacity-80 focus-visible:opacity-80" style={{ flexGrow: item.value, backgroundColor: item.color }} />
                </Tooltip.Trigger>
                <Tooltip.Content side="top">
                  {valueFormat(item.value)} · {item.label} · {formatPercent(share(item.value))}
                </Tooltip.Content>
              </Tooltip.Root>
            ))}
        </div>
        {!hideLegend && (
        <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          {items.map((item) => (
            <li key={item.key} className="min-w-0">
              <div className="flex items-center gap-2 text-paragraph-xs text-text-sub-600">
                <span aria-hidden="true" className="size-2.5 shrink-0 rounded-[3px]" style={{ backgroundColor: item.color }} />
                <span className="truncate">{item.label}</span>
              </div>
              <p className="mt-0.5 text-label-md text-text-strong-950">
                {valueFormat(item.value)} <span className="text-paragraph-xs text-text-soft-400">{formatPercent(share(item.value))}</span>
              </p>
            </li>
          ))}
        </ul>
        )}
      </div>
    </Tooltip.Provider>
  );
}
