export default function SchedulesPage() {
  const schedules = [
    { name: "Daily Cross-Platform Metrics Ingestion", cron: "0 */6 * * *", queue: "analytics_queue", status: "Active" },
    { name: "Midnight Brand Voice Audit", cron: "0 0 * * *", queue: "orchestrator_queue", status: "Active" },
    { name: "Scheduled Social Dispatch Check", cron: "*/5 * * * *", queue: "publishing_queue", status: "Active" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Celery Beat Periodic Schedules</h1>
        <p className="text-slate-400 text-sm">Cron-like background workflows and scheduled post publishing queues.</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-xs uppercase">
            <tr>
              <th className="px-6 py-3">Schedule Name</th>
              <th className="px-6 py-3">Cron Expression</th>
              <th className="px-6 py-3">Assigned Celery Queue</th>
              <th className="px-6 py-3 text-right">State</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {schedules.map((s) => (
              <tr key={s.name}>
                <td className="px-6 py-4 font-medium text-white">{s.name}</td>
                <td className="px-6 py-4 font-mono text-xs text-slate-300">{s.cron}</td>
                <td className="px-6 py-4 font-mono text-xs text-indigo-400">{s.queue}</td>
                <td className="px-6 py-4 text-right">
                  <span className="px-2 py-1 text-xs rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {s.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
