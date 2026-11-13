import type { ComponentType, ReactNode } from "react";
import {
  RiCheckboxCircleLine,
  RiErrorWarningLine,
  RiInformationLine,
  RiAlertLine,
} from "@remixicon/react";
import { cn } from "@/utils/cn";

/**
 * Small building blocks the settings sections share: form fields, callouts
 * and meters. Tokens only, so every piece re-tones in dark mode.
 */

/** A label above its control, with helper text under it and an error in place of the helper. */
export function Field({
  label,
  htmlFor,
  description,
  error,
  optional,
  required,
  className,
  children,
}: {
  label: ReactNode;
  htmlFor?: string;
  description?: ReactNode;
  error?: ReactNode;
  optional?: boolean;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="flex items-baseline gap-1 text-label-sm text-text-strong-950">
        {label}
        {required && <span className="text-primary-base" aria-hidden="true">*</span>}
        {optional && <span className="text-paragraph-xs text-text-soft-400">(optional)</span>}
      </label>
      {children}
      {error ? (
        <p role="alert" className="flex items-start gap-1 text-paragraph-xs text-error-base">
          <RiErrorWarningLine className="mt-px size-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : description ? (
        <p className="text-paragraph-xs text-text-sub-600">{description}</p>
      ) : null}
    </div>
  );
}

/**
 * A setting laid out as a row: what it is on the left, the control on the
 * right. Stacks on narrow screens. Use inside a FramePanel, one per setting,
 * separated by `divide-y`.
 */
export function FieldRow({
  label,
  description,
  htmlFor,
  children,
  className,
}: {
  label: ReactNode;
  description?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between sm:gap-8", className)}>
      <div className="min-w-0 sm:max-w-sm">
        <label htmlFor={htmlFor} className="text-label-sm text-text-strong-950">{label}</label>
        {description && <div className="mt-1 text-paragraph-xs text-text-sub-600">{description}</div>}
      </div>
      <div className="flex min-w-0 flex-col sm:w-80 sm:shrink-0 sm:items-end sm:text-right">{children}</div>
    </div>
  );
}

type CalloutTone = "info" | "warning" | "error" | "success";

const CALLOUT: Record<CalloutTone, { box: string; icon: ComponentType<{ className?: string }> }> = {
  info: { box: "bg-information-lighter text-information-dark ring-information-light", icon: RiInformationLine },
  warning: { box: "bg-warning-lighter text-warning-dark ring-warning-light", icon: RiAlertLine },
  error: { box: "bg-error-lighter text-error-dark ring-error-light", icon: RiErrorWarningLine },
  success: { box: "bg-success-lighter text-success-dark ring-success-light", icon: RiCheckboxCircleLine },
};

/** An inline message: a policy note, a warning, a result. `role` is set for errors and results. */
export function Callout({
  tone = "info",
  title,
  children,
  action,
  className,
}: {
  tone?: CalloutTone;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const { box, icon: Icon } = CALLOUT[tone];
  return (
    <div
      role={tone === "error" ? "alert" : tone === "success" ? "status" : undefined}
      className={cn("flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-paragraph-sm ring-1 ring-inset", box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <p className="text-label-sm">{title}</p>}
        {children && <div className={cn(title && "mt-0.5", "text-paragraph-xs sm:text-paragraph-sm")}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/**
 * Used-of-limit as a thin bar with the figures beside it. `color` is the
 * channel identity colour (CHANNEL_META); a full meter keeps it — reaching a
 * daily cap is the plan working, not an error.
 */
export function Meter({
  value,
  max,
  color,
  label,
  className,
}: {
  value: number;
  max: number;
  color: string;
  /** Screen-reader name, e.g. "Emails sent today". */
  label: string;
  className?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className="h-1.5 min-w-12 flex-1 overflow-hidden rounded-full bg-bg-soft-200"
      >
        <div className="h-full rounded-full transition-[width]" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="shrink-0 whitespace-nowrap text-paragraph-xs tabular-nums text-text-sub-600">
        <span className="text-text-strong-950">{value.toLocaleString("en-US")}</span> / {max.toLocaleString("en-US")}
      </span>
    </div>
  );
}
