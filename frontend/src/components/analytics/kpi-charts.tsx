export function KPICharts({ data }: { data: any }) {
  const bars = [
    { label: "LinkedIn", value: 38, color: "bg-blue-500" },
    { label: "YouTube", value: 52, color: "bg-red-500" },
    { label: "Instagram", value: 64, color: "bg-pink-500" },
    { label: "Threads", value: 29, color: "bg-purple-500" },
    { label: "Facebook", value: 41, color: "bg-indigo-500" },
    { label: "X/Twitter", value: 34, color: "bg-cyan-500" },
    { label: "Pinterest", value: 47, color: "bg-rose-500" },
    { label: "Google BP", value: 22, color: "bg-amber-500" },
  ];

  return (
    <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span className="font-semibold text-slate-200">Cross-Platform Engagement Velocity</span>
        <span>8 Channels Live</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
        {bars.map((b) => (
          <div key={b.label} className="space-y-1">
            <div className="flex justify-between text-xs text-slate-400">
              <span>{b.label}</span>
              <span className="font-mono text-white">{b.value}%</span>
            </div>
            <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
              <div className={`h-full ${b.color} rounded-full`} style={{ width: `${b.value}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
