"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { analyticsApi } from "@/lib/api/endpoints/analytics";
import { settingsApi } from "@/lib/api/endpoints/settings";
import { KPICharts } from "@/components/analytics/kpi-charts";
import { AnomalyAlert } from "@/components/analytics/anomaly-alert";
import { CrossPlatformKPIs, AnalyticsChannelState } from "@marketing-os/contracts";

export default function AnalyticsPage() {
  const [kpis, setKpis] = useState<CrossPlatformKPIs>({
    impressions_total: 0,
    clicks_total: 0,
    ctr_average: 0,
    conversions_total: 0,
    platforms_active: 0,
  });
  const [channels, setChannels] = useState<AnalyticsChannelState[]>([]);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      analyticsApi.getKPIs().catch(() => null),
      analyticsApi.getAnomalies().catch(() => []),
      settingsApi.getAnalyticsChannels().catch(() => []),
    ]).then(([kpiData, anomalyData, channelData]) => {
      if (kpiData) setKpis(kpiData);
      if (Array.isArray(anomalyData)) setAnomalies(anomalyData);
      if (Array.isArray(channelData)) setChannels(channelData);
      setLoading(false);
    });
  }, []);

  const hasData = kpis.impressions_total > 0 || kpis.clicks_total > 0 || channels.some((c) => c.events_count > 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-bloodstone-text">
            Cross-Platform Analytics & Verification
          </h1>
          <p className="text-bloodstone-text-muted text-sm">
            Live multi-channel performance ingested through zero-trust FastMCP analytics services.
          </p>
        </div>
        <div className="text-xs glass-panel px-3 py-1.5 rounded-lg text-bloodstone-mint font-mono">
          Engine: Polars Rolling Z-Score (|Z| &gt; 1.5, N &ge; 5)
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <span className="text-xs font-semibold text-bloodstone-text-muted uppercase">Total Impressions</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-text">{kpis.impressions_total.toLocaleString()}</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold text-bloodstone-text-muted uppercase">Average CTR</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-mint">{(kpis.ctr_average * 100).toFixed(2)}%</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold text-bloodstone-text-muted uppercase">Conversions</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-text">{kpis.conversions_total.toLocaleString()}</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold text-bloodstone-text-muted uppercase">Anomalies Detected</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-mint">
            {anomalies.length > 0 ? `${anomalies.length} Flagged` : "0 (Nominal)"}
          </p>
        </div>
      </div>

      {/* Channel Connectivity & Visibility Matrix */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-bloodstone-text uppercase tracking-wider">
            Channel Sync Status ({channels.filter((c) => c.is_connected).length} / {channels.length || 8} Connected)
          </h2>
          <Link
            href="/settings"
            className="text-xs text-bloodstone-mint hover:underline flex items-center gap-1 font-medium"
          >
            <span>Manage Platform Secrets</span>
            <span>→</span>
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          {channels.map((c) => (
            <div
              key={c.platform}
              className={`p-3 rounded-xl border flex flex-col justify-between transition-all ${
                c.is_connected
                  ? "glass-panel border-glass-specular"
                  : "bg-glass-base/40 border-glass-subtle opacity-70"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold capitalize text-bloodstone-text">{c.platform}</span>
                <span
                  className={`h-2 w-2 rounded-full ${
                    c.is_connected ? "bg-bloodstone-mint shadow-[0_0_6px_#7bf0a7]" : "bg-bloodstone-text-dim"
                  }`}
                />
              </div>
              <div className="mt-3 text-[11px] text-bloodstone-text-muted flex justify-between">
                <span>{c.is_connected ? "Ingestion Active" : "Needs Connection"}</span>
                <span className="font-mono">{c.events_count} events</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Anomalies List */}
      {anomalies.length > 0 ? (
        anomalies.map((a, idx) => <AnomalyAlert key={idx} anomaly={a} />)
      ) : (
        <div className="p-4 glass-panel rounded-xl text-xs text-bloodstone-text-muted flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-bloodstone-mint">✓</span>
            <span>No statistical anomalies detected across active platform telemetry. Distribution remains nominal.</span>
          </div>
          <span className="text-[11px] font-mono text-bloodstone-text-dim">Baseline sample clean</span>
        </div>
      )}

      {/* Empty State Banner if no events ingested */}
      {!hasData && !loading && (
        <div className="p-8 glass-panel rounded-xl text-center space-y-3">
          <div className="text-bloodstone-mint text-lg">📊</div>
          <h3 className="text-sm font-semibold text-bloodstone-text">No Historical Ingestion Events Recorded</h3>
          <p className="text-xs text-bloodstone-text-muted max-w-md mx-auto">
            Connect platform credentials in Settings or dispatch an Orchestrator run in Chat to generate and publish campaigns. Real telemetry will populate here dynamically without demo fixtures.
          </p>
          <div className="pt-1">
            <Link
              href="/chat"
              className="px-4 py-2 glass-emerald text-xs rounded-lg font-semibold text-bloodstone-text inline-block transition"
            >
              Open Orchestrator Chat →
            </Link>
          </div>
        </div>
      )}

      {hasData && <KPICharts data={kpis} />}
    </div>
  );
}
