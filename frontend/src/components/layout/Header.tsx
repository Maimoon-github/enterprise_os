"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck, Cpu, Database, Server, Box, Activity, ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import { SystemServiceStatus } from "@/lib/types";

export const Header = () => {
  const [services, setServices] = useState<SystemServiceStatus[]>([]);
  const [tenant, setTenant] = useState("tenant-enterprise-live");
  const [brand, setBrand] = useState("brand-enterprise");

  useEffect(() => {
    const check = async () => {
      const res = await api.checkHealth();
      setServices(res);
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 flex items-center justify-between px-6">
      {/* Brand & Identity */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-white text-base tracking-tight">ENTERPRISE OS</span>
            <span className="ml-2 text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-400 border border-indigo-800/60">
              Zero-Trust
            </span>
          </div>
        </div>

        {/* Multi-Tenant Scope Badges */}
        <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-slate-800">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <span className="text-slate-500 font-mono">T:</span>
            <span className="font-medium text-slate-200">{tenant}</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <span className="text-slate-500 font-mono">B:</span>
            <span className="font-medium text-slate-200">{brand}</span>
          </div>
        </div>
      </div>

      {/* Real-time Health Indicators */}
      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2">
          {services.map((svc) => (
            <div
              key={svc.name}
              title={`${svc.name}: ${svc.status} (${svc.details || ""})`}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] border transition-all ${
                svc.status === "healthy"
                  ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-400"
                  : svc.status === "degraded"
                  ? "bg-amber-950/40 border-amber-800/60 text-amber-400"
                  : "bg-slate-900 border-slate-800 text-slate-400"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  svc.status === "healthy"
                    ? "bg-emerald-400 animate-pulse"
                    : svc.status === "degraded"
                    ? "bg-amber-400"
                    : "bg-slate-600"
                }`}
              />
              <span className="font-medium">
                {svc.name.includes("Postgres")
                  ? "PGSQL"
                  : svc.name.includes("Ollama")
                  ? "QWEN 7B"
                  : svc.name.includes("FastAPI")
                  ? "API"
                  : svc.name.includes("Portal") || svc.port === 3001
                  ? "SANDBOX WEB"
                  : "SANDBOX"}
              </span>
              {svc.latency_ms ? (
                <span className="text-[10px] opacity-75 font-mono">{svc.latency_ms}ms</span>
              ) : null}
            </div>
          ))}
        </div>

        {/* Sandbox Website Quick Synced Link */}
        <a
          href="http://localhost:3001"
          target="_blank"
          rel="noopener noreferrer"
          title="Open Synced Sandbox Website"
          className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-md bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-xs text-amber-300 transition-all font-mono"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span>SANDBOX :3001</span>
        </a>

        {/* Live Indicator */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-indigo-950/60 border border-indigo-800/80 text-xs text-indigo-300">
          <Activity className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
          <span className="font-semibold tracking-wide">LIVE RUNTIME</span>
        </div>
      </div>
    </header>
  );
};
