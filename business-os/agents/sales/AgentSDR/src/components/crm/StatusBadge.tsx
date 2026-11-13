import { cn } from "@/utils/cn";

const GROUP_TONE: Record<string, string> = {
  interested: "bg-success-lighter text-success-dark ring-success-light",
  not_interested: "bg-error-lighter text-error-dark ring-error-light",
  wrong_poc: "bg-warning-lighter text-warning-dark ring-warning-light",
  other: "bg-bg-weak-50 text-text-sub-600 ring-stroke-soft-200",
  out_of_office: "bg-bg-weak-50 text-text-sub-600 ring-stroke-soft-200",
};

export function groupTone(group: string | null | undefined): string {
  return GROUP_TONE[group ?? ""] ?? "bg-bg-weak-50 text-text-sub-600 ring-stroke-soft-200";
}

export default function StatusBadge({
  label,
  group,
}: {
  label: string | null;
  group?: string | null;
}) {
  if (!label) return <span className="text-text-soft-400">—</span>;
  return (
    <span className={cn("inline-flex h-6 max-w-48 items-center truncate rounded-full px-2.5 text-label-xs ring-1 ring-inset", groupTone(group))} title={label}>
      {label}
    </span>
  );
}
