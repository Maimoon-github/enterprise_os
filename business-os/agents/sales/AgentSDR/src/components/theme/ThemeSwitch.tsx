"use client";

import { RiComputerLine, RiMoonLine, RiSunLine } from "@remixicon/react";
import { cn } from "@/utils/cn";
import { useTheme, type ThemePreference } from "./ThemeProvider";

const OPTIONS: Array<{ value: ThemePreference; label: string; icon: typeof RiSunLine }> = [
  { value: "light", label: "Light", icon: RiSunLine },
  { value: "dark", label: "Dark", icon: RiMoonLine },
  { value: "system", label: "System", icon: RiComputerLine },
];

/** Light / Dark / System as a three-way segmented switch. */
export function ThemeSwitch({ className }: { className?: string }) {
  const { preference, setPreference } = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className={cn("flex gap-0.5 rounded-lg bg-bg-weak-50 p-0.5 ring-1 ring-inset ring-stroke-soft-200", className)}>
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setPreference(value)}
            className={cn(
              "flex h-7 flex-1 items-center justify-center gap-1.5 rounded-md px-2 text-label-xs outline-none transition focus-visible:ring-2 focus-visible:ring-primary-base",
              active ? "bg-bg-white-0 text-text-strong-950 shadow-regular-xs" : "text-text-sub-600 hover:text-text-strong-950",
            )}
          >
            <Icon className="size-3.5" aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** One click between light and dark (from System it flips away from what's showing). */
export function ThemeToggleButton({ className }: { className?: string }) {
  const { resolved, setPreference } = useTheme();
  const next = resolved === "dark" ? "light" : "dark";
  const Icon = resolved === "dark" ? RiSunLine : RiMoonLine;
  return (
    <button
      type="button"
      onClick={() => setPreference(next)}
      aria-label={`Switch to ${next} mode`}
      className={cn("flex size-8 items-center justify-center rounded-lg text-text-soft-400 outline-none transition hover:bg-bg-weak-50 hover:text-text-strong-950 focus-visible:ring-2 focus-visible:ring-primary-base", className)}
    >
      <Icon className="size-[18px]" />
    </button>
  );
}
