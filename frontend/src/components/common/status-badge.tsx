export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-800 text-slate-300 border border-slate-700">
      {status}
    </span>
  );
}
