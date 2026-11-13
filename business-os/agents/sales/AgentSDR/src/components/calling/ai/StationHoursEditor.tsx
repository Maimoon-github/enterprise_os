"use client";

import { useMemo } from "react";
import * as Checkbox from "@/components/alignui/checkbox";
import * as Select from "@/components/alignui/select";
import { timeInputClass } from "@/components/outreach/WorkingHoursModal";
import type { WeeklyHours } from "@/lib/channels/rules";
import { cn } from "@/utils/cn";

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const COMMON_TIMEZONES = ["Asia/Kolkata", "Asia/Singapore", "Asia/Dubai", "Europe/London", "Europe/Berlin", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Australia/Sydney", "UTC"];

export function hoursSummary(hours: WeeklyHours): string {
  return `${hours.days.map((day) => DAY_LABELS[day]).join(", ")} ${hours.start}–${hours.end} (${hours.timezone})`;
}

/** Time zone, days and a start–end window: the same shape as the Sending rules' calling hours. */
export function StationHoursEditor({ value, onChange, disabled }: { value: WeeklyHours; onChange: (value: WeeklyHours) => void; disabled?: boolean }) {
  const zones = useMemo(() => {
    const all = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
    return [...new Set([value.timezone, ...COMMON_TIMEZONES, ...all])];
  }, [value.timezone]);
  const set = (patch: Partial<WeeklyHours>) => onChange({ ...value, ...patch });
  const invalid = value.start >= value.end || value.days.length === 0;
  return (
    <div className="flex flex-col gap-2.5">
      <Select.Root size="small" value={value.timezone} onValueChange={(timezone) => set({ timezone })} disabled={disabled}>
        <Select.Trigger aria-label="Time zone"><Select.Value /></Select.Trigger>
        <Select.Content>
          {zones.map((zone) => <Select.Item key={zone} value={zone}>{zone}</Select.Item>)}
        </Select.Content>
      </Select.Root>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Days">
        {DAY_LABELS.map((label, day) => {
          const on = value.days.includes(day);
          return (
            <label key={label} className={cn("flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-label-xs ring-1 ring-inset", on ? "bg-primary-alpha-10 text-primary-base ring-primary-alpha-16" : "text-text-sub-600 ring-stroke-soft-200")}>
              <Checkbox.Root
                checked={on}
                disabled={disabled}
                onCheckedChange={(checked) => set({ days: checked === true ? [...value.days, day].sort((a, b) => a - b) : value.days.filter((d) => d !== day) })}
              />
              {label}
            </label>
          );
        })}
      </div>
      <div className="flex items-center gap-2">
        <input type="time" aria-label="Start" value={value.start} disabled={disabled} onChange={(event) => set({ start: event.target.value })} className={cn(timeInputClass, value.start >= value.end && "ring-error-base")} />
        <span className="shrink-0 text-paragraph-xs text-text-soft-400">to</span>
        <input type="time" aria-label="End" value={value.end} disabled={disabled} onChange={(event) => set({ end: event.target.value })} className={cn(timeInputClass, value.start >= value.end && "ring-error-base")} />
      </div>
      {invalid && <p className="text-paragraph-xs text-error-base">Pick at least one day, and an end after the start.</p>}
    </div>
  );
}

export const hoursInvalid = (hours: WeeklyHours): boolean => hours.start >= hours.end || hours.days.length === 0;
