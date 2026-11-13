"use client";

import { useEffect, useRef, useState } from "react";

export type ActionsMenuItem = {
  key: string;
  label: string;
  onSelect: () => void;
  tone?: "default" | "danger";
  disabled?: boolean;
};

/** Kebab (3-dot) action menu — click-outside-to-close dropdown, modeled on Select.tsx. */
export default function ActionsMenu({ items }: { items: ActionsMenuItem[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="More actions"
        className={`w-8 h-8 flex items-center justify-center rounded-lg border transition-colors ${
          open ? "border-stroke-sub-300 bg-bg-weak-50" : "border-stroke-soft-200 hover:bg-bg-weak-50"
        }`}
      >
        <svg className="w-4 h-4 text-text-strong-950/60" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 5.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM10 11.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM10 17.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-1.5 w-44 rounded-xl border border-stroke-soft-200 bg-bg-white-0 shadow-xl shadow-slate-200/60 dark:shadow-black/40 overflow-hidden py-1">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={`w-full text-left px-3 py-2 text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                item.tone === "danger" ? "text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10" : "text-text-strong-950 hover:bg-bg-weak-50"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
