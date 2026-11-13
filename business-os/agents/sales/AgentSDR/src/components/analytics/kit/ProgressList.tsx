import Link from "next/link";
import { cn } from "@/utils/cn";
import { STATUS } from "../theme";

/**
 * Rows with a status dot, label, value, a muted subline and — when `progress`
 * is given — a thin 6px progress bar with the percentage. Rows with `href` are
 * links. Status colour appears only on the dot/bar and always beside the label
 * (and `icon`, if given), so state never rests on colour alone.
 *
 * Props: `items` [{ key, label, value (string|number), subline?, tone?
 * "neutral"|"good"|"warning"|"serious"|"critical"|"accent", progress? 0..1,
 * icon?, href? }].
 */
export type ProgressTone = "neutral" | "good" | "warning" | "serious" | "critical" | "accent";
export type ProgressItem = {
  key: string;
  label: string;
  value: string | number;
  subline?: string;
  tone?: ProgressTone;
  progress?: number;
  icon?: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  href?: string;
};

const TONE_COLOR: Record<ProgressTone, string> = {
  neutral: "var(--chart-muted)",
  good: STATUS.good,
  warning: STATUS.warning,
  serious: STATUS.serious,
  critical: STATUS.critical,
  accent: "#335cff",
};

export function ProgressList({ items }: { items: ProgressItem[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {items.map((item) => {
        const color = TONE_COLOR[item.tone ?? "neutral"];
        const Icon = item.icon;
        const body = (
          <>
            <div className="flex items-center gap-2.5">
              {Icon ? <Icon className="size-[18px] shrink-0" style={{ color }} aria-hidden="true" /> : <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />}
              <span className="min-w-0 flex-1 truncate text-label-sm text-text-strong-950">{item.label}</span>
              <span className="text-label-sm tabular-nums text-text-strong-950">{typeof item.value === "number" ? item.value.toLocaleString("en-US") : item.value}</span>
            </div>
            {item.subline && <p className="ml-7 mt-0.5 truncate text-paragraph-xs text-text-sub-600">{item.subline}</p>}
            {item.progress !== undefined && (
              <div className="ml-7 mt-2 flex items-center gap-3">
                <div className="h-1.5 flex-1 rounded-full bg-bg-weak-50">
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, item.progress * 100))}%`, backgroundColor: color }} />
                </div>
                <span className="w-9 text-right text-paragraph-xs tabular-nums text-text-sub-600">{Math.round(item.progress * 100)}%</span>
              </div>
            )}
          </>
        );
        return (
          <li key={item.key}>
            {item.href ? (
              <Link href={item.href} className={cn("block rounded-lg px-2 py-2.5 outline-none transition hover:bg-bg-weak-50 focus-visible:ring-2 focus-visible:ring-primary-base")}>
                {body}
              </Link>
            ) : (
              <div className="px-2 py-2.5">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
