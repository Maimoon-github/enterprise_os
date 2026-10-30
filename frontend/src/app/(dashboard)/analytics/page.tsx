"use client";

import { useEffect, useState } from "react";
import { analyticsApi } from "@/lib/api/endpoints/analytics";
import { KPICharts } from "@/components/analytics/kpi-charts";
import { AnomalyAlert } from "@/components/analytics/anomaly-alert";

export default function AnalyticsPage() {
  const [kpis, setKpis] = useState({
    impressions_total: 142500,
    clicks_total: 4820,
    ctr_average: 0.0338,
    conversions_total: 310,
    platforms_active: 8,
  });
  const [anomalies, setAnomalies] = useState<any[]>([]);

  useEffect(() => {
    analyticsApi.getKPIs().then((data) => {
      if (data) setKpis(data);
    }).catch(() => {});

    analyticsApi.getAnomalies().then((data) => {
      if (Array.isArray(data)) setAnomalies(data);
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cross-Platform Analytics & Anomalies</h1>
          <p className="text-slate-400 text-sm">Aggregated multi-channel engagement, conversions, and automated Polars z-score anomaly alerts.</p>
        </div>
        <div className="text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-slate-300 font-mono">
          Engine: Polars Rolling Z-Score (|Z| &gt; 1.5)
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Total Impressions</span>
          <p className="text-2xl font-bold mt-2">{kpis.impressions_total.toLocaleString()}</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Average CTR</span>
          <p className="text-2xl font-bold mt-2 text-emerald-400">{(kpis.ctr_average * 100).toFixed(2)}%</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Conversions</span>
          <p className="text-2xl font-bold mt-2">{kpis.conversions_total.toLocaleString()}</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs font-semibold text-slate-400 uppercase">Anomalies Detected</span>
          <p className="text-2xl font-bold mt-2 text-indigo-400">
            {anomalies.length > 0 ? `${anomalies.length} Flagged` : "0 (Nominal)"}
          </p>
        </div>
      </div>

      {anomalies.map((a, idx) => (
        <AnomalyAlert key={idx} anomaly={a} />
      ))}

      <KPICharts data={kpis} />
    </div>
  );
}
