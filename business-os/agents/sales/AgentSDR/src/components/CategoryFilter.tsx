"use client";

import { useEffect, useRef, useState } from "react";
import categoriesData from "@/data/categories.json";

export const NULL_CATEGORY = "__null__";

type CountMap = Record<string, number>;

type Props = {
  countryCode: string;
  c1: string;
  c2: string;
  c3: string;
  onChange: (updates: Record<string, string>) => void;
};

function fmt(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

export default function CategoryFilter({ countryCode, c1, c2, c3, onChange }: Props) {
  const [c1Counts, setC1Counts] = useState<CountMap>({});
  const [c2Counts, setC2Counts] = useState<CountMap>({});
  const [c3Counts, setC3Counts] = useState<CountMap>({});

  useEffect(() => {
    fetch(`/api/categories/counts?countryCode=${countryCode}&level=c1`)
      .then((r) => r.json())
      .then(setC1Counts)
      .catch(() => {});
  }, [countryCode]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: effect resets/seeds local state when props or open state change; deriving during render would change timing
    if (!c1 || c1 === NULL_CATEGORY) { setC2Counts({}); return; }
    fetch(`/api/categories/counts?countryCode=${countryCode}&level=c2&c1=${encodeURIComponent(c1)}`)
      .then((r) => r.json())
      .then(setC2Counts)
      .catch(() => {});
  }, [countryCode, c1]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: effect resets/seeds local state when props or open state change; deriving during render would change timing
    if (!c1 || !c2) { setC3Counts({}); return; }
    fetch(`/api/categories/counts?countryCode=${countryCode}&level=c3&c1=${encodeURIComponent(c1)}&c2=${encodeURIComponent(c2)}`)
      .then((r) => r.json())
      .then(setC3Counts)
      .catch(() => {});
  }, [countryCode, c1, c2]);

  const c2Options = c1 && c1 !== NULL_CATEGORY
    ? (categoriesData.l2[c1 as keyof typeof categoriesData.l2] ?? [])
    : [];
  const c3Options = c1 && c2
    ? (categoriesData.l3[`${c1} > ${c2}` as keyof typeof categoriesData.l3] ?? [])
    : [];

  return (
    <div className="flex flex-col gap-2">
      <CategorySelect
        placeholder="All Categories"
        value={c1}
        options={categoriesData.l1}
        counts={c1Counts}
        showNull
        onSelect={(v) => onChange({ c1: v, c2: "", c3: "" })}
        onClear={() => onChange({ c1: "", c2: "", c3: "" })}
      />

      {c1 && c1 !== NULL_CATEGORY && c2Options.length > 0 && (
        <CategorySelect
          placeholder={`All ${c1}`}
          value={c2}
          options={c2Options}
          counts={c2Counts}
          onSelect={(v) => onChange({ c2: v, c3: "" })}
          onClear={() => onChange({ c2: "", c3: "" })}
        />
      )}

      {c1 && c2 && c3Options.length > 0 && (
        <CategorySelect
          placeholder={`All ${c2}`}
          value={c3}
          options={c3Options}
          counts={c3Counts}
          onSelect={(v) => onChange({ c3: v })}
          onClear={() => onChange({ c3: "" })}
        />
      )}
    </div>
  );
}

type SelectProps = {
  placeholder: string;
  value: string;
  options: string[];
  counts: CountMap;
  showNull?: boolean;
  onSelect: (v: string) => void;
  onClear: () => void;
};

function CategorySelect({ placeholder, value, options, counts, showNull, onSelect, onClear }: SelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const displayLabel = value === NULL_CATEGORY ? "Uncategorized" : value;

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`
          w-full flex items-center justify-between gap-2 rounded-lg border text-left
          px-3 py-2.5 text-sm transition-all duration-150 focus:outline-none
          ${value ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 font-medium" : "border-stroke-soft-200 bg-bg-white-0 text-text-strong-950/50 hover:border-stroke-sub-300"}
          ${open ? "ring-2 ring-indigo-300 dark:ring-indigo-500/30 border-indigo-400" : ""}
        `}
      >
        <span className="truncate">{value ? displayLabel : placeholder}</span>
        <div className="flex items-center gap-1 shrink-0">
          {value && (
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); onClear(); setOpen(false); }}
              className="w-4 h-4 flex items-center justify-center rounded-full text-indigo-400 hover:bg-indigo-200 dark:hover:bg-indigo-500/25 hover:text-indigo-700 dark:hover:text-indigo-400 transition-colors text-xs"
            >
              ×
            </span>
          )}
          <svg className={`w-4 h-4 text-text-strong-950/50 transition-transform duration-200 ${open ? "rotate-180" : ""}`} viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
          </svg>
        </div>
      </button>

      {open && (
        <div className="absolute z-50 mt-1.5 w-56 rounded-xl border border-stroke-soft-200 bg-bg-white-0 shadow-xl shadow-slate-200/60 dark:shadow-black/40 overflow-hidden max-h-72 overflow-y-auto">
          {/* All / clear */}
          <button
            type="button"
            onClick={() => { onClear(); setOpen(false); }}
            className={`w-full text-left px-3 py-2.5 text-sm border-b border-stroke-soft-200 transition-colors ${
              !value ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 font-medium" : "text-text-strong-950/50 hover:bg-bg-weak-50"
            }`}
          >
            {placeholder}
          </button>

          {/* Named options — filter to only those with counts once counts are loaded */}
          {(Object.keys(counts).length > 0 ? options.filter((o) => counts[o] !== undefined) : options).map((opt) => {
            const cnt = counts[opt];
            return (
              <button
                key={opt}
                type="button"
                onClick={() => { onSelect(opt); setOpen(false); }}
                className={`w-full text-left flex items-center justify-between gap-2 px-3 py-2.5 text-sm transition-colors ${
                  opt === value ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 font-medium" : "text-text-strong-950 hover:bg-bg-weak-50"
                }`}
              >
                <span className="truncate min-w-0 flex-1">{opt}</span>
                {cnt !== undefined && (
                  <span className={`text-xs tabular-nums shrink-0 ${opt === value ? "text-indigo-400" : "text-text-strong-950/50"}`}>
                    {fmt(cnt)}
                  </span>
                )}
              </button>
            );
          })}

          {/* Uncategorized — no count */}
          {showNull && (
            <>
              <div className="border-t border-stroke-soft-200" />
              <button
                type="button"
                onClick={() => { onSelect(NULL_CATEGORY); setOpen(false); }}
                className={`w-full text-left px-3 py-2.5 text-sm italic transition-colors ${
                  value === NULL_CATEGORY ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 font-medium not-italic" : "text-text-strong-950/50 hover:bg-bg-weak-50"
                }`}
              >
                Uncategorized
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
