"use client";

import { useEffect, useRef } from "react";

export function LeadSelectCheckbox({
  checked,
  indeterminate,
  onChange,
  onClick,
  ariaLabel,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: (checked: boolean) => void;
  onClick?: (e: React.MouseEvent) => void;
  ariaLabel: string;
}) {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ref.current) ref.current.indeterminate = Boolean(indeterminate);
  }, [indeterminate, checked]);

  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      onClick={onClick}
      aria-label={ariaLabel}
      className="h-4 w-4 rounded border-stroke-sub-300 text-blue-600 dark:text-blue-400 focus:ring-blue-500 cursor-pointer"
    />
  );
}
