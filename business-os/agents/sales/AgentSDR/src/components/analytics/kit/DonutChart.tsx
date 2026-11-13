"use client";

import type { ComponentType, CSSProperties } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "@/utils/cn";
import { formatCompact, formatPercent, MUTED, SURFACE } from "../theme";
import { EmptyChart } from "./EmptyChart";

/**
 * Part-to-whole at a glance: a thin donut with the total in the middle and a
 * legend of label, value and share beside it (below on narrow cards). The
 * legend doubles as the table view — every number is readable as text.
 *
 * Rules it enforces (see the dataviz notes in theme.ts):
 * - At most `maxSlices` (default 6) segments; the smallest fold into "Other"
 *   in the de-emphasis gray. A donut is for shares, not for comparing close
 *   values — use BarList for that.
 * - Slices keep the order of `items`, so colour follows the entity and a
 *   fixed order keeps adjacent colours distinguishable.
 * - 2px surface gaps between slices; per-slice hover tooltip.
 *
 * Props: `items` [{ key, label, value, color, icon? }] (an icon replaces the
 * legend dot — required when the colour is a status colour), `centerLabel`
 * (caption under the total), `valueFormat`, `size` (px, default 164),
 * `maxSlices`, `emptyLabel` / `emptyDescription` (the empty state's two lines).
 */
export type DonutItem = {
  key: string;
  label: string;
  value: number;
  color: string;
  icon?: ComponentType<{ className?: string; style?: CSSProperties }>;
};

function fold(items: DonutItem[], maxSlices: number): DonutItem[] {
  const nonZero = items.filter((i) => i.value > 0);
  if (nonZero.length <= maxSlices) return nonZero;
  const keep = new Set([...nonZero].sort((a, b) => b.value - a.value).slice(0, maxSlices - 1).map((i) => i.key));
  const rest = nonZero.filter((i) => !keep.has(i.key));
  return [
    ...nonZero.filter((i) => keep.has(i.key)),
    { key: "__other", label: `Other (${rest.length})`, value: rest.reduce((s, i) => s + i.value, 0), color: MUTED },
  ];
}

type SliceTooltipArgs = { active?: boolean; payload?: ReadonlyArray<{ payload?: DonutItem }> };

export function DonutChart({
  items,
  centerLabel,
  valueFormat = formatCompact,
  size = 164,
  maxSlices = 6,
  emptyLabel = "Nothing in this period.",
  emptyDescription,
  className,
}: {
  items: DonutItem[];
  centerLabel?: string;
  valueFormat?: (value: number) => string;
  size?: number;
  maxSlices?: number;
  emptyLabel?: string;
  emptyDescription?: string;
  className?: string;
}) {
  const slices = fold(items, maxSlices);
  const total = slices.reduce((s, i) => s + i.value, 0);
  if (total === 0) return <EmptyChart height={size} title={emptyLabel} description={emptyDescription} />;
  const share = (value: number) => formatPercent(value / total);

  const tooltip = ({ active, payload }: SliceTooltipArgs) => {
    const item = active ? payload?.[0]?.payload : undefined;
    if (!item) return null;
    return (
      <div className="rounded-lg bg-bg-white-0 px-3 py-2 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200">
        <p className="flex items-center gap-2 text-paragraph-xs text-text-sub-600">
          <span aria-hidden="true" className="size-2 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </p>
        <p className="mt-1 text-label-sm tabular-nums text-text-strong-950">
          {valueFormat(item.value)} <span className="text-paragraph-xs text-text-sub-600">· {share(item.value)}</span>
        </p>
      </div>
    );
  };

  return (
    // A container query, not a viewport one: side by side only when the card itself is wide enough.
    <div className={cn("@container", className)}>
    <div className="flex flex-col items-center gap-5 @sm:flex-row @sm:gap-6">
      <div
        role="img"
        aria-label={`${centerLabel ?? "Total"} ${valueFormat(total)}: ${slices.map((s) => `${s.label} ${valueFormat(s.value)} (${share(s.value)})`).join(", ")}`}
        className="relative shrink-0"
        style={{ width: size, height: size }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius="74%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              cornerRadius={3}
              stroke={SURFACE}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((s) => (
                <Cell key={s.key} fill={s.color} className="outline-none transition-opacity hover:opacity-80" />
              ))}
            </Pie>
            <Tooltip content={tooltip} cursor={false} wrapperStyle={{ outline: "none", zIndex: 10 }} />
          </PieChart>
        </ResponsiveContainer>
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-title-h5 font-semibold leading-none tracking-tight text-text-strong-950">{valueFormat(total)}</span>
          {centerLabel && <span className="mt-1 max-w-[70%] text-center text-paragraph-xs text-text-sub-600">{centerLabel}</span>}
        </div>
      </div>

      <ul className="w-full min-w-0 flex-1 divide-y divide-stroke-soft-200">
        {slices.map((s) => {
          const Icon = s.icon;
          return (
            <li key={s.key} className="flex items-center gap-2.5 py-2 first:pt-0 last:pb-0">
              {Icon ? (
                <Icon aria-hidden="true" className="size-4 shrink-0" style={{ color: s.color }} />
              ) : (
                <span aria-hidden="true" className="ml-1 mr-0.5 size-2 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
              )}
              <span className="min-w-0 flex-1 truncate text-paragraph-sm text-text-sub-600" title={s.label}>{s.label}</span>
              <span className="text-label-sm tabular-nums text-text-strong-950">{valueFormat(s.value)}</span>
              <span className="w-10 text-right text-paragraph-xs tabular-nums text-text-soft-400">{share(s.value)}</span>
            </li>
          );
        })}
      </ul>
    </div>
    </div>
  );
}
