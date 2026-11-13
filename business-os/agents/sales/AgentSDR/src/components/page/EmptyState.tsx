import type { ComponentType, ReactNode } from "react";
import { cn } from "@/utils/cn";

/**
 * The one empty state: an icon in a soft chip, a short title that says what
 * is missing, one line on what to do about it, and an optional action.
 * Use inside a FramePanel or a split pane; it centres itself.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact = false,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  /** Less vertical padding, for small cards and list panes. */
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "px-4 py-8" : "px-6 py-16", className)}>
      <span className="flex size-10 items-center justify-center rounded-xl bg-bg-weak-50 ring-1 ring-inset ring-stroke-soft-200">
        <Icon className="size-5 text-text-sub-600" />
      </span>
      <p className="mt-3 text-label-sm text-text-strong-950">{title}</p>
      {description && <p className="mt-1 max-w-sm text-paragraph-sm text-text-sub-600">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
