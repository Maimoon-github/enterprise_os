import { cn } from "@/utils/cn";
import { formatCompact, formatPercent, ordinalRamp } from "../theme";

/**
 * Conversion funnel over ordered stages, coloured on the ordinal blue ramp
 * (light to dark). Each stage shows its value, a "% of previous" chip (step
 * conversion) and a bar proportional to the first stage. Renders as an <ol>.
 *
 * Props:
 * - stages [{ key, label, value }]
 * - layout "rows" (default; vertical stack, fits a 4-col card) or "tiles"
 *   (a row of stage cells with a coloured left border, then bars — use in a
 *   wide card)
 * - valueFormat (default formatCompact)
 */
export type FunnelStage = { key: string; label: string; value: number; stepLabel?: string };

function StepChip({ step }: { step: number | null }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-md bg-bg-weak-50 px-1.5 py-0.5 text-paragraph-xs text-text-sub-600">
      <span aria-hidden="true">↳</span> {formatPercent(step, 1)}<span className="hidden sm:inline"> of previous</span>
    </span>
  );
}

export function FunnelChart({ stages, layout = "rows", valueFormat = formatCompact }: { stages: FunnelStage[]; layout?: "rows" | "tiles"; valueFormat?: (value: number) => string }) {
  const colors = ordinalRamp(stages.length);
  const top = stages[0]?.value ?? 0;
  const stepOf = (i: number) => (i > 0 && stages[i - 1].value > 0 ? stages[i].value / stages[i - 1].value : null);
  const widthOf = (value: number) => (top > 0 ? Math.max((value / top) * 100, value > 0 ? 1.5 : 0) : 0);
  const bar = (i: number) => (
    <div className="h-2 w-full rounded-full bg-bg-weak-50">
      <div className="h-full rounded-r-[4px] rounded-l-full" style={{ width: `${widthOf(stages[i].value)}%`, backgroundColor: colors[i] }} />
    </div>
  );

  if (layout === "tiles") {
    return (
      <ol>
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
          {stages.map((stage, i) => (
            <li key={stage.key} className="border-l-2 pl-3" style={{ borderColor: colors[i] }}>
              <p className="text-paragraph-sm text-text-sub-600">{stage.label}</p>
              <p className="mt-1 text-title-h5 font-semibold text-text-strong-950">{valueFormat(stage.value)}</p>
              <div className="mt-1.5 h-6">{i > 0 && <StepChip step={stepOf(i)} />}</div>
            </li>
          ))}
        </div>
        <div className="mt-4 flex flex-col gap-1.5" aria-hidden="true">
          {stages.map((stage, i) => (
            <div key={stage.key}>{bar(i)}</div>
          ))}
        </div>
      </ol>
    );
  }

  return (
    <ol className="flex flex-col gap-5">
      {stages.map((stage, i) => (
        <li key={stage.key}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span aria-hidden="true" className="h-4 w-0.5 shrink-0 rounded-full" style={{ backgroundColor: colors[i] }} />
              <span className="truncate text-paragraph-sm text-text-sub-600">{stage.label}</span>
            </div>
            <div className="flex items-center gap-2">
              {i > 0 && <StepChip step={stepOf(i)} />}
              <span className={cn("min-w-10 text-right text-label-md text-text-strong-950")}>{valueFormat(stage.value)}</span>
            </div>
          </div>
          <div className="mt-2">{bar(i)}</div>
        </li>
      ))}
    </ol>
  );
}
