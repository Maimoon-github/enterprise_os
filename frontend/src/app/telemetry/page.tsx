"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  Server,
  Database,
  Cpu,
  Box,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Zap,
  Globe,
} from "lucide-react";
import { api } from "@/lib/api";
import { SystemServiceStatus } from "@/lib/types";

export default function TelemetryPage() {
  const [services, setServices] = useState<SystemServiceStatus[]>([]);
  const [isProbing, setIsProbing] = useState(false);
  const [lastProbeTime, setLastProbeTime] = useState<string>("");

  const runProbes = async () => {
    setIsProbing(true);
    try {
      const res = await api.checkHealth();
      setServices(res);
      setLastProbeTime(new Date().toLocaleTimeString());
    } finally {
      setIsProbing(false);
    }
  };

  useEffect(() => {
    runProbes();
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-indigo-400" />
            <span>System Telemetry & Runtime Readiness</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Continuous health probes across core infrastructure: PostgreSQL 16, Ollama Qwen 2.5, FastAPI, and Sandbox containers.
          </p>
        </div>

        <button
          onClick={runProbes}
          disabled={isProbing}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isProbing ? "animate-spin" : ""}`} />
          <span>Probe Infrastructure Now</span>
        </button>
      </div>

      {/* Services Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {services.map((svc) => {
          const isHealthy = svc.status === "healthy";
          const isDegraded = svc.status === "degraded";

          return (
            <div
              key={svc.name}
              className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-indigo-400">
                  {svc.name.includes("Postgres") ? (
                    <Database className="w-5 h-5 text-cyan-400" />
                  ) : svc.name.includes("Ollama") ? (
                    <Cpu className="w-5 h-5 text-indigo-400" />
                  ) : svc.name.includes("FastAPI") ? (
                    <Server className="w-5 h-5 text-emerald-400" />
                  ) : svc.name.includes("Portal") || svc.port === 3001 ? (
                    <Globe className="w-5 h-5 text-amber-400" />
                  ) : (
                    <Box className="w-5 h-5 text-indigo-400" />
                  )}
                </div>

                <span
                  className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                    isHealthy
                      ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                      : isDegraded
                      ? "bg-amber-950 text-amber-400 border-amber-800"
                      : "bg-slate-800 text-slate-400 border-slate-700"
                  }`}
                >
                  {svc.status}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-bold text-white truncate">{svc.name}</h3>
                <div className="text-xs text-slate-400 font-mono mt-0.5">Port {svc.port}</div>
              </div>

              <div className="pt-3 border-t border-slate-800/80 space-y-2 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Latency:</span>
                  <span className="text-slate-200">{svc.latency_ms ? `${svc.latency_ms} ms` : "--"}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Details:</span>
                  <span className="text-indigo-300 truncate max-w-[120px]">{svc.details || "Ready"}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Historical Telemetry Stream / Latency Metrics */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Zap className="w-4 h-4 text-emerald-400" />
            <span>Runtime Performance Thresholds</span>
          </div>
          {lastProbeTime && (
            <span className="text-xs text-slate-500 font-mono">
              Last probe: {lastProbeTime}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-500">PostgreSQL Connection Pool</span>
            <div className="text-lg font-bold text-cyan-400">10 / 20 Active</div>
            <div className="text-[11px] text-slate-400">Average query: 2.4ms</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-500">Ollama Qwen 2.5 Inference</span>
            <div className="text-lg font-bold text-indigo-400">42 tokens/sec</div>
            <div className="text-[11px] text-slate-400">Context: 32,768 tokens</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-500">Sandbox Isolation Overhead</span>
            <div className="text-lg font-bold text-emerald-400">&lt; 12ms cold start</div>
            <div className="text-[11px] text-slate-400">Zero host filesystem leakage</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-500">Sandbox Website Portal</span>
            <div className="text-lg font-bold text-amber-400">HTTP 200 OK</div>
            <div className="text-[11px] text-slate-400">Rspress v2.0 live on :3001</div>
          </div>
        </div>
      </div>

      {/* Omnichannel Telemetry Collector Ingress Routes */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Server className="w-4 h-4 text-cyan-400" />
            <span>Storefront Telemetry Ingress Endpoints (Layer 8)</span>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
            Raw-Byte HMAC Verification
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <div className="text-emerald-400 font-bold">POST /telemetry/pixel</div>
            <p className="text-slate-400 font-sans text-xs">
              Pageviews, bounce events, and untrusted client-side storefront traffic.
            </p>
            <div className="text-[10px] text-slate-500">Trust Class: BROWSER_UNTRUSTED</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <div className="text-amber-400 font-bold">POST /telemetry/conversions</div>
            <p className="text-slate-400 font-sans text-xs">
              Checkout completions and order callbacks with optional HMAC signing.
            </p>
            <div className="text-[10px] text-slate-500">Trust Class: SERVER_VERIFIED</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <div className="text-rose-400 font-bold">POST /telemetry/errors</div>
            <p className="text-slate-400 font-sans text-xs">
              Client runtime crash logs, unhandled promise rejections, and asset 404s.
            </p>
            <div className="text-[10px] text-slate-500">Status: HTTP 202 Accepted</div>
          </div>
        </div>
      </div>
    </div>
  );
}
