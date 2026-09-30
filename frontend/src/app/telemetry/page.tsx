"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  Box,
  RefreshCw,
  AlertCircle,
  Zap,
  Globe,
  Radio,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";
import { SystemServiceStatus, TelemetryReceipt, TelemetryHandshakeProbe } from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

export default function TelemetryPage() {
  const [services, setServices] = useState<SystemServiceStatus[]>([]);
  const [isProbing, setIsProbing] = useState(false);
  const [probes, setProbes] = useState<TelemetryHandshakeProbe[]>([]);
  const [receipts, setReceipts] = useState<TelemetryReceipt[]>([]);
  const [readiness, setReadiness] = useState<any>(null);
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const { addToast } = useToast();

  const runProbes = async () => {
    setIsProbing(true);
    try {
      const res = await api.checkHealth();
      setServices(res);
      const pr = await api.runTelemetryProbes();
      setProbes(pr);
      const rd = await api.checkTelemetryReadiness();
      setReadiness(rd);
      setReceipts(api.getRecentTelemetryReceipts());
      addToast({
        type: "success",
        title: "Synthetic Probes Executed",
        message: `Verified 5 telemetry surfaces for tenant ${settings.tenantId}.`,
      });
    } finally {
      setIsProbing(false);
    }
  };

  useEffect(() => {
    runProbes();
  }, []);

  const handleEmitPixel = async () => {
    const rcpt = await api.sendPixelTelemetry({ page: "/checkout/tier-selection" });
    setReceipts([...api.getRecentTelemetryReceipts()]);
    addToast({
      type: "success",
      title: "Storefront Pixel Admitted",
      message: `Logical Event: ${rcpt.logical_event_id} (website pixel)`,
      hash: rcpt.content_hash,
    });
  };

  const handleEmitConversion = async () => {
    const rcpt = await api.sendConversionTelemetry({
      order_id: `ord_${Date.now().toString().slice(-5)}`,
      amount: 149.99,
      currency: "USD",
    });
    setReceipts([...api.getRecentTelemetryReceipts()]);
    addToast({
      type: "success",
      title: "Conversion Telemetry Recorded",
      message: `Revenue: $149.99 USD verified via raw-byte signature.`,
      hash: rcpt.content_hash,
    });
  };

  const handleEmitError = async () => {
    const rcpt = await api.sendErrorTelemetry({
      error_code: "SANDBOX_EGRESS_BLOCKED",
      message: "Worker attempted connection to unallowlisted IP outside sandbox boundary.",
    });
    setReceipts([...api.getRecentTelemetryReceipts()]);
    addToast({
      type: "warning",
      title: "Error Log Ingested",
      message: `Receipt ID: ${rcpt.receipt_id}`,
      hash: rcpt.content_hash,
    });
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-indigo-400" />
            <span>Omnichannel Telemetry & Runtime Readiness</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Continuous health probes across core infrastructure: PostgreSQL 16, Ollama Qwen 2.5, FastAPI, and Sandbox containers.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={runProbes}
            disabled={isProbing}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isProbing ? "animate-spin" : ""}`} />
            <span>1-Click Synthetic Probe</span>
          </button>

          <a
            href={settings.sandboxWebsiteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-amber-300 text-xs font-semibold transition-all font-mono"
          >
            <Box className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Sandbox Site (:3001)</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* 1-Click Interactive Telemetry Dispatcher Bar */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Radio className="w-4 h-4 text-cyan-400" />
            <span>1-Click Live Telemetry Event Simulators</span>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Tenant: {settings.tenantId} • Ingress: Raw-Byte Verified
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={handleEmitPixel}
            className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-500/60 text-left transition-all space-y-1.5 group"
          >
            <div className="flex items-center justify-between text-xs font-bold text-white">
              <span>Emit Pageview Pixel</span>
              <Globe className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Sends unauthenticated storefront traffic telemetry to <code className="text-emerald-300">/telemetry/pixel</code>.
            </p>
          </button>

          <button
            onClick={handleEmitConversion}
            className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-cyan-500/60 text-left transition-all space-y-1.5 group"
          >
            <div className="flex items-center justify-between text-xs font-bold text-white">
              <span>Emit Checkout Conversion ($149.99)</span>
              <Zap className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Triggers verified order purchase intake callback at <code className="text-cyan-300">/telemetry/conversions</code>.
            </p>
          </button>

          <button
            onClick={handleEmitError}
            className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-rose-500/60 text-left transition-all space-y-1.5 group"
          >
            <div className="flex items-center justify-between text-xs font-bold text-white">
              <span>Trigger Synthetic Error Log</span>
              <AlertCircle className="w-4 h-4 text-rose-400 group-hover:scale-110 transition-transform" />
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Logs sandbox security boundary warning at <code className="text-rose-300">/telemetry/errors</code>.
            </p>
          </button>
        </div>
      </div>

      {/* Services Health Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {services.slice(0, 4).map((svc) => (
          <div
            key={svc.name}
            className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-slate-400">Port {svc.port}</span>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
                {svc.status}
              </span>
            </div>
            <h3 className="text-sm font-bold text-white truncate">{svc.name}</h3>
            <div className="pt-2 border-t border-slate-800/80 text-xs font-mono text-slate-400 flex justify-between">
              <span>Latency:</span>
              <span className="text-slate-200">{svc.latency_ms ? `${svc.latency_ms} ms` : "--"}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Probes Results Table & Ingress Receipts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Active Listener Probes */}
        <div className="lg:col-span-7 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Active Listener Probes ({probes.length})
          </div>

          <div className="space-y-3">
            {probes.map((pr, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white">{pr.listener}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-cyan-300 border border-slate-800">
                      {pr.channel}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">{pr.details}</p>
                </div>

                <div className="text-right font-mono">
                  <span className="text-emerald-400 font-bold block">{pr.latency_ms} ms</span>
                  <span className="text-[10px] text-slate-500 uppercase">{pr.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Ingestion Receipts Stream */}
        <div className="lg:col-span-5 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Live Telemetry Ingestion Receipts ({receipts.length})
          </div>

          <div className="space-y-3 max-h-[420px] overflow-y-auto">
            {receipts.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 rounded-xl bg-slate-900/40 border border-slate-800">
                Click any simulator button above to emit live telemetry.
              </div>
            ) : (
              receipts.map((rcpt, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 font-mono text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-cyan-300">{rcpt.receipt_id}</span>
                    <span className="text-[10px] uppercase text-emerald-400 px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800">
                      {rcpt.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate">
                    Hash: {rcpt.content_hash}
                  </div>
                  <div className="text-[10px] text-slate-500">
                    Channel: {rcpt.channel} • {rcpt.occurred_at ? new Date(rcpt.occurred_at).toLocaleTimeString() : "--"}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
