"use client";

import * as React from "react";
import { cn } from "@/utils/cn";

/**
 * AlignUI-styled on/off switch. A plain button with role="switch" (no Radix
 * dependency): Space/Enter toggle it like any button, and aria-checked
 * carries the state for assistive tech.
 */
export const Root = React.forwardRef<
  HTMLButtonElement,
  Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
    checked: boolean;
    onCheckedChange?: (checked: boolean) => void;
  }
>(({ checked, onCheckedChange, className, disabled, onClick, ...rest }, ref) => (
  <button
    ref={ref}
    type="button"
    role="switch"
    aria-checked={checked}
    disabled={disabled}
    onClick={(event) => {
      onClick?.(event);
      if (!event.defaultPrevented) onCheckedChange?.(!checked);
    }}
    className={cn(
      "group/switch relative inline-flex h-5 w-8 shrink-0 items-center rounded-full p-0.5 outline-none transition duration-200 ease-out",
      "focus-visible:ring-2 focus-visible:ring-primary-alpha-16 focus-visible:ring-offset-1",
      checked ? "bg-primary-base hover:bg-primary-darker" : "bg-bg-soft-200 hover:bg-bg-sub-300",
      disabled && "cursor-not-allowed opacity-50 hover:bg-bg-soft-200",
      className,
    )}
    {...rest}
  >
    <span
      aria-hidden="true"
      className={cn(
        "block size-4 rounded-full bg-static-white shadow-regular-xs transition-transform duration-200 ease-out",
        checked ? "translate-x-3" : "translate-x-0",
      )}
    />
  </button>
));
Root.displayName = "SwitchRoot";
