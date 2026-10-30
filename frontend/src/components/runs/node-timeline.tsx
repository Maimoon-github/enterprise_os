export function NodeTimeline({ events }: { events: any[] }) {
  return (
    <div className="space-y-2">
      {events.map((ev, i) => (
        <div key={i} className="text-xs p-2 bg-slate-900 border border-slate-800 rounded flex items-center justify-between">
          <span className="font-mono text-indigo-400">{ev.node}</span>
          <span className="text-slate-500">{ev.status}</span>
        </div>
      ))}
    </div>
  );
}
