import Link from "next/link";

export function Sidebar() {
  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 p-6 flex flex-col justify-between">
      <div>
        <div className="flex items-center gap-2 mb-8">
          <div className="h-6 w-6 rounded bg-indigo-600 flex items-center justify-center font-bold text-xs">AG</div>
          <span className="font-semibold tracking-wide text-sm">Marketing OS</span>
        </div>
      </div>
    </aside>
  );
}
