"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  Activity,
  Sliders,
  ExternalLink,
  Box,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { SystemServiceStatus } from "@/lib/types";
import { getStoredSettings, subscribeSettings, EnterpriseSettings } from "@/lib/settings";
import { SettingsModal } from "@/components/settings/SettingsModal";

export const Header = () => {
  const [services, setServices] = useState<SystemServiceStatus[]>([]);
  const [settings, setSettings] = useState<EnterpriseSettings>(getStoredSettings());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    const unsub = subscribeSettings((newSettings) => {
      setSettings(newSettings);
    });
    return unsub;
  }, []);

  useEffect(() => {
    const check = async () => {
      const res = await api.checkHealth();
      setServices(res);
    };
    check();
    const interval = setInterval(
      check,
      settings.autoRefreshSeconds ? settings.autoRefreshSeconds * 1000 : 10000
    );
    return () => clearInterval(interval);
  }, [settings.autoRefreshSeconds]);

  return (
    <>
      <header className="h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-6">
        {/* Brand & Identity */}
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-all">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-white text-base tracking-tight">ENTERPRISE OS</span>
              <span className="ml-2 text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-400 border border-indigo-800/60">
                Zero-Trust
              </span>
            </div>
          </Link>

          {/* Dynamic Tenant & Brand Scoping */}
          <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-slate-800">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-300">
              <span className="text-slate-500 font-mono">T:</span>
              <span className="font-medium text-slate-200">{settings.tenantId}</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-300">
              <span className="text-slate-500 font-mono">B:</span>
              <span className="font-medium text-slate-200">{settings.brandId}</span>
            </div>
          </div>
        </div>

        {/* Real-time Health Indicators & Actions */}
        <div className="flex items-center gap-3">
          <div className="hidden xl:flex items-center gap-2">
            {services.slice(0, 4).map((svc) => (
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
                    ? "API :8000"
                    : "SANDBOX :18091"}
                </span>
                {svc.latency_ms ? (
                  <span className="text-[10px] opacity-75 font-mono">{svc.latency_ms}ms</span>
                ) : null}
              </div>
            ))}
          </div>

          {/* LINK TO SANDBOX ENGINE */}
          <Link
            href="/sandbox"
            title="Launch live AIO Sandbox Engine (:18091)"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white text-xs font-semibold shadow-md shadow-amber-600/20 transition-all group"
          >
            <Box className="w-3.5 h-3.5 text-white animate-pulse" />
            <span className="hidden sm:inline font-mono">SANDBOX DAEMON</span>
            <span className="sm:hidden font-mono">:18091</span>
            <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
          </Link>

          {/* System Settings & Customization Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            title="Customize System Endpoints & Parameters"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 transition-all"
          >
            <Sliders className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden md:inline">Customize</span>
          </button>

          {/* Live Indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-950/60 border border-indigo-800/80 text-xs text-indigo-300">
            <Activity className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
            <span className="font-semibold tracking-wide hidden sm:inline">LIVE</span>
          </div>
        </div>
      </header>

      {/* Global Customization Modal */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </>
  );
};
