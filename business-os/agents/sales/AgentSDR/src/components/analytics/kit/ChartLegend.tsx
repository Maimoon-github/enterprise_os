import { cn } from "@/utils/cn";
import { formatCompact } from "../theme";

/**
 * Legend rendered outside the plot, in ChartCard's `legend` slot. Always used
 * for two or more series; a single series needs none.
 *
 * Props: `items` [{ label, color, value? }], `shape` "swatch" (bars, areas) or
 * "line" (lines) mirrors the mark. `value` is an optional total shown after the
 * label in a text token — the colour lives only on the key beside it.
 */
export type LegendItem = { label: string; color: string; value?: number };

export function ChartLegend({ items, shape = "swatch", className }: { items: LegendItem[]; shape?: "swatch" | "line"; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2 text-paragraph-xs text-text-sub-600">
          <span
            aria-hidden="true"
            className={cn("shrink-0", shape === "line" ? "h-0.5 w-3.5 rounded-full" : "size-2.5 rounded-[3px]")}
            style={{ backgroundColor: item.color }}
          />
          <span>{item.label}</span>
          {item.value !== undefined && <span className="text-label-xs text-text-strong-950">{formatCompact(item.value)}</span>}
        </li>
      ))}
    </ul>
  );
}
