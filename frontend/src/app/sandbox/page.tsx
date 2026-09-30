"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  ExternalLink,
  ShieldCheck,
  Terminal,
  Globe,
  Layers,
  CheckCircle2,
  RefreshCw,
  Cpu,
  FileCode,
  Lock,
} from "lucide-react";
import { api } from "@/lib/api";
import { SandboxServiceInfo } from "@/lib/types";

export default function SandboxPortalPage() {
  const [sandboxInfo, setSandboxInfo] = useState<SandboxServiceInfo>(api.getSandboxInfo());
  const [activeTab, setActiveTab] = useState<"embedded" | "overview">("embedded");
  const [latency, setLatency] = useState<number>(1.4);
  const [isSyncing, setIsSyncing] = useState(false);

  const syncSandbox = async () => {
    setIsSyncing(true);
    try {
      const services = await api.checkHealth();
      const sb = services.find((s) => s.name.includes("Sandbox") || s.port === 3001);
      if (sb && sb.latency_ms) setLatency(sb.latency_ms);
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    syncSandbox();
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Box className="w-6 h-6 text-amber-400" />
            <span>AIO Agent Sandbox Environment & Synced Portal</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Zero-trust execution container. Hosts browser automation, shell execution, file virtualization, and documentation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={syncSandbox}
            disabled={isSyncing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin" : ""}`} />
            <span>Sync Sandbox ({latency}ms)</span>
          </button>

          <a
            href={sandboxInfo.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white text-xs font-semibold shadow-lg shadow-amber-600/20 transition-all"
          >
            <span>Open Sandbox Portal</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Status & Synced Links Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-medium tracking-wider">Container Status</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>ONLINE & ISOLATED</span>
          </div>
          <div className="text-xs text-slate-400 font-mono">
            Bound to localhost:3001 • Latency: {latency}ms
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-medium tracking-wider">Synced Frontend URL</span>
            <Globe className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-lg font-bold font-mono text-cyan-300 truncate">
            {sandboxInfo.url}
          </div>
          <div className="text-xs text-slate-400">
            Rspress Documentation & API Reference Hub
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-medium tracking-wider">Security Boundary</span>
            <Lock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            Level 6 (Strict)
          </div>
          <div className="text-xs text-slate-400">
            cgroups + namespaces + ephemeral RAM scrub
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-3 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab("embedded")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "embedded"
              ? "bg-amber-950/80 text-amber-300 border border-amber-800/80"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Live Embedded Sandbox Portal
        </button>
        <button
          onClick={() => setActiveTab("overview")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "overview"
              ? "bg-amber-950/80 text-amber-300 border border-amber-800/80"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Micro-Agent Capabilities Matrix
        </button>
      </div>

      {/* Tab 1: Live Embedded Portal */}
      {activeTab === "embedded" && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl space-y-0">
          <div className="h-10 bg-slate-900/90 border-b border-slate-800 px-4 flex items-center justify-between text-xs text-slate-400 font-mono">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-rose-500/80" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
              <span className="ml-2 text-slate-300">{sandboxInfo.url}/</span>
            </div>
            <a
              href={sandboxInfo.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-400 hover:text-amber-300 flex items-center gap-1 font-semibold"
            >
              <span>Pop out</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <div className="relative w-full h-[650px] bg-slate-950">
            <iframe
              src={sandboxInfo.url}
              title="Sandbox Portal"
              className="w-full h-full border-0"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            />
          </div>
        </div>
      )}

      {/* Tab 2: Capabilities Matrix */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-sm">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span>Core Sandbox Capabilities</span>
            </div>

            <div className="space-y-3">
              {sandboxInfo.features.map((feature, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 flex items-start gap-3"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{feature}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-sm">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Worker Engine Containment Allocation</span>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex justify-between font-mono">
                  <span className="font-bold text-indigo-400">W_DEV (Development)</span>
                  <span className="text-emerald-400">S_CODE micro-tool</span>
                </div>
                <p className="text-slate-400">AST parsing, ESLint execution, TypeScript compilation, and unit test runners.</p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex justify-between font-mono">
                  <span className="font-bold text-cyan-400">W_COMP (Compliance)</span>
                  <span className="text-emerald-400">S_SCRAPE micro-tool</span>
                </div>
                <p className="text-slate-400">DOM extraction, accessibility audits, WCAG 2.1 AA evaluation, and legal claim linters.</p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex justify-between font-mono">
                  <span className="font-bold text-amber-400">W_STRAT (Strategy)</span>
                  <span className="text-emerald-400">S_ALLOC micro-tool</span>
                </div>
                <p className="text-slate-400">Mathematical portfolio optimization, marginal ROAS matrix computation.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
