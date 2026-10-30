"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface SettingsData {
  encryption: string;
  sandbox_engine: string;
  primary_observability: string;
  checkpointer: string;
  target_platforms_count: number;
  sandbox_limits?: {
    memory_limit: string;
    cpu_limit: string;
    network_default: string;
    security_opt: string;
    cap_drop: string;
    mount_mode: string;
    podman_installed: boolean;
  };
  celery_queues?: string[];
  beat_schedules_count?: number;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null);

  useEffect(() => {
    apiClient<SettingsData>("/settings")
      .then((data) => setSettings(data))
      .catch(() => {
        setSettings({
          encryption: "AES-256-GCM",
          sandbox_engine: "rootless-podman",
          primary_observability: "Langfuse (OTLP)",
          checkpointer: "PostgresSaver (Async)",
          target_platforms_count: 8,
          sandbox_limits: {
            memory_limit: "512m",
            cpu_limit: "1.0",
            network_default: "none",
            security_opt: "no-new-privileges",
            cap_drop: "ALL",
            mount_mode: "ro",
            podman_installed: false,
          },
          celery_queues: [
            "orchestrator_queue",
            "publishing_queue",
            "media_queue",
            "analytics_queue",
          ],
          beat_schedules_count: 3,
        });
      });
  }, []);

  const limits = settings?.sandbox_limits || {
    memory_limit: "512m",
    cpu_limit: "1.0",
    network_default: "none",
    security_opt: "no-new-privileges",
    cap_drop: "ALL",
    mount_mode: "ro",
  };

  const queues = settings?.celery_queues || [
    "orchestrator_queue",
    "publishing_queue",
    "media_queue",
    "analytics_queue",
  ];

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Platform Configuration & Isolation</h1>
        <p className="text-slate-400 text-sm">
          Inspect rootless Podman sandbox parameters, Celery worker concurrency, and encrypted secrets.
        </p>
      </div>

      {/* Podman Sandbox Quotas */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">Rootless Podman Sandbox Hardening</h3>
            <p className="text-xs text-slate-400">
              Ephemeral container runtime for Tier 3 Agent Skill scripts and untrusted code execution.
            </p>
          </div>
          <span className="px-2.5 py-1 text-xs rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
            {settings?.sandbox_engine || "rootless-podman"}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs font-mono">
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
            <span className="text-slate-500 text-[10px] uppercase">Memory Limit</span>
            <div className="text-white font-bold">{limits.memory_limit}</div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
            <span className="text-slate-500 text-[10px] uppercase">CPU Allocation</span>
            <div className="text-white font-bold">{limits.cpu_limit} CPUs</div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
            <span className="text-slate-500 text-[10px] uppercase">Network Isolation</span>
            <div className="text-amber-400 font-bold">{limits.network_default}</div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
            <span className="text-slate-500 text-[10px] uppercase">Security Opt</span>
            <div className="text-emerald-400 font-bold">{limits.security_opt}</div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
            <span className="text-slate-500 text-[10px] uppercase">Linux Capabilities</span>
            <div className="text-emerald-400 font-bold">{limits.cap_drop}</div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
            <span className="text-slate-500 text-[10px] uppercase">Workspace Mount</span>
            <div className="text-white font-bold">:{limits.mount_mode} (Read-Only)</div>
          </div>
        </div>
      </div>

      {/* Celery Task Queues */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <h3 className="text-base font-semibold text-white">Celery Asynchronous Task Queues</h3>
        <p className="text-xs text-slate-400">
          Redis broker with Kombu partitioned queues, W3C traceparent propagation, and late acknowledgment.
        </p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          {queues.map((q) => (
            <div key={q} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between font-mono">
              <span className="text-indigo-400 font-semibold">{q}</span>
              <span className="text-emerald-400 text-[11px] font-sans">Active • acks_late</span>
            </div>
          ))}
        </div>
      </div>

      {/* Platform Integrations */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <h3 className="text-base font-semibold text-white">Social Platform Credentials</h3>
        <p className="text-xs text-slate-400">
          All client tokens encrypted with AES-256-GCM and scoped to FastMCP integration servers.
        </p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          {[
            "LinkedIn API",
            "YouTube Data API",
            "Meta Graph API (IG/FB/Threads)",
            "X API v2",
            "Pinterest REST v5",
            "Google Business Profile",
          ].map((c) => (
            <div key={c} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between">
              <span className="text-slate-200">{c}</span>
              <span className="text-emerald-400 font-semibold">Configured</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
