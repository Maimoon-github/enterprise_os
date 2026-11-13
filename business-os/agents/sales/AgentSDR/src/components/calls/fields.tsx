"use client";

import { useId } from "react";
import * as Input from "@/components/alignui/input";
import { cn } from "@/utils/cn";

/** An inline error for a modal or a section; `role="alert"` so it is announced. */
export function FormError({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div role="alert" className={cn("rounded-lg bg-error-lighter px-3 py-2 text-paragraph-xs text-error-dark ring-1 ring-inset ring-error-light", className)}>
      {children}
    </div>
  );
}

/** A labelled AlignUI text input for the calling modals. */
export function TextField({
  label,
  value,
  onChange,
  className,
  ...rest
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "size">) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-label-sm text-text-strong-950">{label}</label>
      <Input.Root size="small">
        <Input.Wrapper>
          <Input.Input id={id} value={value} onChange={(event) => onChange(event.target.value)} {...rest} />
        </Input.Wrapper>
      </Input.Root>
    </div>
  );
}
