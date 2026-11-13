"use client";

import { useNavigation } from "./NavigationProvider";

export default function TableLoadingOverlay() {
  const { isPending } = useNavigation();
  if (!isPending) return null;

  return (
    <div className="absolute inset-0 z-20 bg-bg-white-0/60 backdrop-blur-[1px] flex items-center justify-center">
      <div className="flex items-center gap-3 bg-bg-white-0 border border-stroke-soft-200 shadow-lg rounded-xl px-5 py-3">
        <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm font-medium text-text-strong-950">Loading results…</span>
      </div>
    </div>
  );
}
