import { RiBarChartBoxLine } from "@remixicon/react";

/**
 * The "nothing to plot" state for a chart card body. Keeps the chart's height
 * so the layout doesn't jump. Props: `title`, `description`, `height` (px).
 */
export function EmptyChart({
  title = "No data for this period",
  description = "Nothing happened in this date range. Try a wider range.",
  height = 260,
}: {
  title?: string;
  description?: string;
  height?: number;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl bg-bg-weak-50 px-6 text-center" style={{ height }}>
      <RiBarChartBoxLine className="size-6 text-text-soft-400" aria-hidden="true" />
      <p className="mt-2 text-label-sm text-text-strong-950">{title}</p>
      <p className="mt-0.5 max-w-xs text-paragraph-xs text-text-sub-600">{description}</p>
    </div>
  );
}
