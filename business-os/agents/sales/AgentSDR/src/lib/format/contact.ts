export function relativeTime(date: string | Date | null): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  const diffMs = d.getTime() - Date.now();
  const diffMin = Math.round(diffMs / 60000);
  const abs = Math.abs(diffMin);
  const unit = abs < 60 ? { n: abs, label: "min" } : abs < 60 * 24 ? { n: Math.round(abs / 60), label: "hr" } : { n: Math.round(abs / (60 * 24)), label: "day" };
  const suffix = unit.n === 1 ? "" : "s";
  return diffMin <= 0 ? `${unit.n} ${unit.label}${suffix} ago` : `in ${unit.n} ${unit.label}${suffix}`;
}

export function fullName(first: string | null, last: string | null): string {
  return [first, last].filter(Boolean).join(" ") || "—";
}

export const CONFIDENCE_REVIEW_THRESHOLD_CLIENT = 0.7;
