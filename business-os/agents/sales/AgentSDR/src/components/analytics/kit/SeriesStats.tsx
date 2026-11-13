import { DeltaPill } from "./DeltaPill";

/**
 * The chart legend with numbers: per series a colour dot, an UPPERCASE label,
 * the value and (optionally) a delta pill. This IS the legend for 2+ series;
 * for a single series pass one item to show just value + delta. Place it in
 * ChartCard's `legend` slot. The colour lives on the dot only, never on text.
 *
 * Props: `items` [{ label, color, value (string), metric? { value, previous }, upIsGood? }].
 */
export type SeriesStat = { label: string; color: string; value: string; metric?: { value: number | null; previous: number | null }; upIsGood?: boolean };

export function SeriesStats({ items }: { items: SeriesStat[] }) {
  return (
    <ul className="flex flex-wrap items-start gap-x-8 gap-y-3">
      {items.map((item) => (
        <li key={item.label} className="flex items-start gap-2">
          <span aria-hidden="true" className="mt-1.5 size-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
          <div>
            <p className="text-subheading-2xs uppercase text-text-soft-400">{item.label}</p>
            <div className="mt-0.5 flex items-center gap-2">
              <span className="text-title-h6 font-semibold text-text-strong-950">{item.value}</span>
              {item.metric && <DeltaPill metric={item.metric} upIsGood={item.upIsGood} />}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
