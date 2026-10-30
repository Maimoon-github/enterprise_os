export default function DashboardOverviewPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Executive Control Plane</h1>
        <p className="text-slate-400 text-sm">Real-time status of multi-agent marketing operations and platform health.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold uppercase text-slate-400">Active Campaigns</span>
          <p className="text-2xl font-bold mt-2">12</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold uppercase text-amber-400">Pending Approvals</span>
          <p className="text-2xl font-bold mt-2 text-amber-300">3</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold uppercase text-slate-400">Platforms Synced</span>
          <p className="text-2xl font-bold mt-2">8 / 8</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold uppercase text-slate-400">Trajectory Gate</span>
          <p className="text-2xl font-bold mt-2 text-emerald-400">98.4%</p>
        </div>
      </div>
    </div>
  );
}
