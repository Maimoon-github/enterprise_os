export default function DashboardOverviewPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-bloodstone-text">Executive Control Plane</h1>
        <p className="text-bloodstone-text-muted text-sm">Real-time status of multi-agent marketing operations and platform health.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-text-muted">Active Campaigns</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-text">12</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-mint">Pending Approvals</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-mint">3</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-text-muted">Platforms Synced</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-text">8 / 8</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-text-muted">Trajectory Gate</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-mint">98.4%</p>
        </div>
      </div>
    </div>
  );
}
