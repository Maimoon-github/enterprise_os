import { formatPercent } from "../theme";

/**
 * A rate for a table cell: the percentage as text plus a slim inline bar,
 * scaled against `max` (the largest rate in the column) so rows compare.
 *
 * Props: `rate` (0..1 or null), `max` (0..1), `color` bar fill.
 */
export function RateCell({ rate, max, color }: { rate: number | null; max: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-12 text-paragraph-sm tabular-nums text-text-strong-950">{formatPercent(rate)}</span>
      <span aria-hidden="true" className="hidden h-1.5 w-20 rounded-full bg-bg-weak-50 sm:block">
        <span className="block h-full rounded-full" style={{ width: `${max > 0 ? ((rate ?? 0) / max) * 100 : 0}%`, backgroundColor: color }} />
      </span>
    </div>
  );
}
