export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Cross-Platform Analytics & Anomalies</h1>
        <p className="text-slate-400 text-sm">Aggregated multi-channel engagement, conversions, and automated Polars z-score anomaly alerts.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Total Impressions</span>
          <p className="text-2xl font-bold mt-2">142,500</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Average CTR</span>
          <p className="text-2xl font-bold mt-2 text-emerald-400">3.38%</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Conversions</span>
          <p className="text-2xl font-bold mt-2">310</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Anomalies Detected</span>
          <p className="text-2xl font-bold mt-2 text-indigo-400">0 (Nominal)</p>
        </div>
      </div>
    </div>
  );
}
