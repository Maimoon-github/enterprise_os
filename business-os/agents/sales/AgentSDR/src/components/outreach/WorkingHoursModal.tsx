"use client";

import { useState } from "react";
import { RiTimeLine } from "@remixicon/react";

import * as Button from "@/components/alignui/button";
import * as Checkbox from "@/components/alignui/checkbox";
import * as Modal from "@/components/alignui/modal";
import * as Select from "@/components/alignui/select";
import { Callout, Field } from "@/components/settings/SettingsKit";
import type { WorkingHours } from "@/lib/outreach/schema";
import { cn } from "@/utils/cn";

const DAYS: { key: keyof WorkingHours["days"]; label: string }[] = [
  { key: "monday", label: "Monday" },
  { key: "tuesday", label: "Tuesday" },
  { key: "wednesday", label: "Wednesday" },
  { key: "thursday", label: "Thursday" },
  { key: "friday", label: "Friday" },
  { key: "saturday", label: "Saturday" },
  { key: "sunday", label: "Sunday" },
];

// Asia/Kolkata first — it matches DEFAULT_WORKING_HOURS in schema.ts and is
// where sending actually happens, so it should be the pre-selected option.
const COMMON_TIMEZONES = [
  "Asia/Kolkata",
  "Asia/Singapore",
  "Europe/London",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "UTC",
];

/** A native time input in the AlignUI field style; the error ring marks a window that ends before it starts. */
export const timeInputClass =
  "h-9 w-full min-w-0 rounded-lg bg-bg-white-0 px-2.5 text-paragraph-sm tabular-nums text-text-strong-950 shadow-regular-xs outline-none ring-1 ring-inset ring-stroke-soft-200 transition hover:bg-bg-weak-50 focus:shadow-button-important-focus focus:ring-stroke-strong-950 disabled:bg-bg-weak-50 disabled:text-text-disabled-300 disabled:shadow-none disabled:ring-transparent";

export default function WorkingHoursModal({
  mailboxId,
  mailboxAddress,
  initial,
  onClose,
  onSaved,
}: {
  mailboxId: string;
  mailboxAddress?: string;
  initial: WorkingHours;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [value, setValue] = useState<WorkingHours>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateDay(key: keyof WorkingHours["days"], patch: Partial<WorkingHours["days"][typeof key]>) {
    setValue((prev) => ({ ...prev, days: { ...prev.days, [key]: { ...prev.days[key], ...patch } } }));
  }

  const enabledCount = DAYS.filter(({ key }) => value.days[key].enabled).length;
  const inverted = DAYS.filter(({ key }) => value.days[key].enabled && value.days[key].from >= value.days[key].to);
  const timezones = COMMON_TIMEZONES.includes(value.timezone) ? COMMON_TIMEZONES : [value.timezone, ...COMMON_TIMEZONES];

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/outreach/mailboxes/${mailboxId}/working-hours`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workingHours: value }),
      });
      if (!res.ok) {
        setError("The sending hours were not saved. Please try again.");
        return;
      }
      onSaved();
      onClose();
    } catch {
      setError("Could not reach the server. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal.Root open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content size="max-w-lg">
        <Modal.Header icon={RiTimeLine}>
          <Modal.Title>Sending hours</Modal.Title>
          <Modal.Description>
            {mailboxAddress ? `${mailboxAddress} only sends` : "This mailbox only sends"} inside this window. Emails due outside it wait for the next open slot.
          </Modal.Description>
        </Modal.Header>
        <Modal.Body className="space-y-5">
          <Field label="Timezone" description="The days and times below are in this timezone.">
            <Select.Root size="small" value={value.timezone} onValueChange={(tz) => setValue((prev) => ({ ...prev, timezone: tz }))}>
              <Select.Trigger aria-label="Timezone">
                <Select.Value />
              </Select.Trigger>
              <Select.Content>
                {timezones.map((tz) => (
                  <Select.Item key={tz} value={tz}>
                    {tz}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>

          <fieldset>
            <legend className="text-label-sm text-text-strong-950">Days</legend>
            <p className="mt-0.5 text-paragraph-xs text-text-sub-600">
              {enabledCount === 0 ? "No days are on — this mailbox will not send." : `Sends on ${enabledCount} ${enabledCount === 1 ? "day" : "days"} a week.`}
            </p>
            <ul className="mt-3 divide-y divide-stroke-soft-200 rounded-xl ring-1 ring-inset ring-stroke-soft-200">
              {DAYS.map(({ key, label }) => {
                const day = value.days[key];
                const bad = day.enabled && day.from >= day.to;
                return (
                  <li key={key} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
                    <label className="flex w-32 shrink-0 cursor-pointer items-center gap-2.5">
                      <Checkbox.Root checked={day.enabled} onCheckedChange={(c) => updateDay(key, { enabled: c === true })} />
                      <span className={cn("text-label-sm", day.enabled ? "text-text-strong-950" : "text-text-soft-400")}>{label}</span>
                    </label>
                    {day.enabled ? (
                      <div className="flex min-w-0 flex-1 items-center gap-2">
                        <input
                          type="time"
                          aria-label={`${label} start`}
                          value={day.from}
                          onChange={(e) => updateDay(key, { from: e.target.value })}
                          className={cn(timeInputClass, bad && "ring-error-base")}
                        />
                        <span className="shrink-0 text-paragraph-xs text-text-soft-400">to</span>
                        <input
                          type="time"
                          aria-label={`${label} end`}
                          value={day.to}
                          onChange={(e) => updateDay(key, { to: e.target.value })}
                          className={cn(timeInputClass, bad && "ring-error-base")}
                        />
                      </div>
                    ) : (
                      <span className="flex-1 text-paragraph-sm text-text-soft-400">Not sending</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </fieldset>

          {inverted.length > 0 && (
            <Callout tone="warning">
              {inverted.map((d) => d.label).join(", ")} {inverted.length === 1 ? "ends" : "end"} before {inverted.length === 1 ? "it starts" : "they start"}, so nothing will send then.
            </Callout>
          )}
          {error && <Callout tone="error">{error}</Callout>}
        </Modal.Body>
        <Modal.Footer>
          <Button.Root variant="neutral" mode="stroke" size="small" onClick={onClose}>
            Cancel
          </Button.Root>
          <Button.Root variant="primary" mode="filled" size="small" disabled={saving} onClick={handleSave}>
            {saving ? "Saving…" : "Save hours"}
          </Button.Root>
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}
