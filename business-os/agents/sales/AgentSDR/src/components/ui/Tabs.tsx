"use client";

/** Pill-style tab bar — first shared tabs primitive in the codebase. Controlled by the parent. */
export default function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1 bg-bg-white-0 border border-stroke-soft-200 rounded-xl p-1 w-fit">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            active === tab.id
              ? "bg-indigo-600 text-white"
              : "text-text-strong-950/60 hover:text-text-strong-950 hover:bg-bg-weak-50"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
