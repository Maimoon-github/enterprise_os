"use client";

import { Area, AreaChart, Line, LineChart, ResponsiveContainer } from "recharts";
import { ACCENT, SURFACE } from "../theme";

/**
 * Tiny axis-less trend for KPI cells and table rows. Decorative (aria-hidden):
 * the values live in the chart or table it accompanies.
 *
 * Props: `data` number[] (2+ points), `color` (default slot 1), `type` "line" |
 * "area", `height` px (default 28), `className` for width, `highlightLast`
 * draws the current (last) point as an accent dot — pair with a gray `color`
 * for the "history in gray, now in accent" look.
 */
export function Sparkline({
  data,
  color = ACCENT,
  type = "line",
  height = 28,
  className,
  highlightLast,
}: {
  data: number[];
  color?: string;
  type?: "line" | "area";
  height?: number;
  className?: string;
  highlightLast?: boolean;
}) {
  if (data.length < 2) return null;
  const points = data.map((value, index) => ({ index, value }));
  const last = points.length - 1;
  const dot = highlightLast
    ? (p: { cx?: number; cy?: number; index?: number }) => (p.index === last && p.cx !== undefined ? <circle key="end" cx={p.cx} cy={p.cy} r={3.5} fill={ACCENT} stroke={SURFACE} strokeWidth={2} /> : <g key={`d${p.index}`} />)
    : false;
  const margin = { top: 4, right: 4, bottom: 4, left: 2 };
  return (
    <div aria-hidden="true" className={className ?? "w-20"} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        {type === "area" ? (
          <AreaChart data={points} margin={margin}>
            <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={color} fillOpacity={0.1} dot={dot} isAnimationActive={false} />
          </AreaChart>
        ) : (
          <LineChart data={points} margin={margin}>
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={dot} strokeLinecap="round" isAnimationActive={false} />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
