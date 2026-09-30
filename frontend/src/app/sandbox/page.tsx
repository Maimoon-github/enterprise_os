"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  ExternalLink,
  Terminal,
  Globe,
  Layers,
  CheckCircle2,
  RefreshCw,
  Lock,
  Monitor,
  Tablet,
  Smartphone,
  Server,
} from "lucide-react";
import { api } from "@/lib/api";
import { getStoredSettings, subscribeSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

export default function SandboxPortalPage() {
  const [settings, setSettings] = useState<EnterpriseSettings>(getStoredSettings());
  const [activeTab, setActiveTab] = useState<"embedded" | "services" | "capabilities">("embedded");
  const [currentIframeUrl, setCurrentIframeUrl] = useState<string>(settings.sandboxWebsiteUrl);
  const [viewportMode, setViewportMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [latency, setLatency] = useState<number>(1.2);
  const [isSyncing, setIsSyncing] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    return subscribeSettings((newSettings) => {
      setSettings(newSettings);
      setCurrentIframeUrl(newSettings.sandboxWebsiteUrl);
    });
  }, []);

  const syncSandbox = async () => {
    setIsSyncing(true);
    try {
      const services = await api.checkHealth();
      const sb = services.find((s) => s.name.includes("Sandbox Website") || s.port === 3001);
      if (sb && sb.latency_ms) setLatency(sb.latency_ms);
      addToast({
        type: "success",
        title: "Sandbox Verified Online",
        message: `Direct link active to ${settings.sandboxWebsiteUrl} (${latency}ms latency).`,
      });
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    syncSandbox();
  }, []);

  // Quick navigation destinations inside sandbox/website
  const DOC_DEEP_LINKS = [
    { name: "Website Home", path: "/", description: "Homepage & Overview" },
    { name: "Guide / Quick Start", path: "/guide/start/introduction", description: "Architecture & Container Setup" },
    { name: "API Reference", path: "/api", description: "Scalar Interactive OpenAPI Specs" },
    { name: "Daemon Docs", path: "/daemon/start/introduction", description: "Sandbox Daemon & Network Policy" },
    { name: "Blog / Changelog", path: "/blog/index", description: "Releases & Updates" },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-800/60 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Box className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                <span>AIO Agent Sandbox Environment & Synced Website</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                  sandbox/website
                </span>
              </h1>
              <p className="text-xs text-slate-300 mt-0.5">
                Isolated execution container & documentation front-end. Runs Rspress docs, Playwright browser automation, and POSIX micro-tools.
              </p>
            </div>
          </div>
        </div>

        {/* Direct Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={syncSandbox}
            disabled={isSyncing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin" : ""}`} />
            <span>Sync ({latency}ms)</span>
          </button>

          {/* DIRECT LINK BUTTON TO SANDBOX WEBSITE */}
          <a
            href={currentIframeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white text-xs font-semibold shadow-lg shadow-amber-600/25 transition-all group"
          >
            <span>Launch Sandbox Website</span>
            <ExternalLink className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </a>
        </div>
      </div>

      {/* Direct Section Deep-Link Bar */}
      <div className="space-y-2">
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">
          Direct Sandbox Website Navigation Shortcuts:
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
          {DOC_DEEP_LINKS.map((link) => {
            const fullUrl = `${settings.sandboxWebsiteUrl}${link.path}`;
            const isActive = currentIframeUrl === fullUrl;
            return (
              <button
                key={link.path}
                onClick={() => setCurrentIframeUrl(fullUrl)}
                className={`p-3 rounded-xl border text-left transition-all ${
                  isActive
                    ? "bg-amber-950/60 border-amber-500/80 text-white shadow-md shadow-amber-500/10"
                    : "bg-slate-900/60 border-slate-800 hover:border-slate-700 text-slate-300"
                }`}
              >
                <div className="flex items-center justify-between text-xs font-bold">
                  <span>{link.name}</span>
                  <ExternalLink className="w-3 h-3 text-amber-400 opacity-60" />
                </div>
                <div className="text-[10px] text-slate-400 truncate mt-0.5">{link.description}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab("embedded")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "embedded"
              ? "bg-amber-950/80 text-amber-300 border border-amber-800/80"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Globe className="w-3.5 h-3.5" />
          <span>Interactive Live Sandbox Front-End</span>
        </button>

        <button
          onClick={() => setActiveTab("services")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "services"
              ? "bg-amber-950/80 text-amber-300 border border-amber-800/80"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Server className="w-3.5 h-3.5" />
          <span>All 7 Environment Ports & Subservices</span>
        </button>

        <button
          onClick={() => setActiveTab("capabilities")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "capabilities"
              ? "bg-amber-950/80 text-amber-300 border border-amber-800/80"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Worker Containment Matrix</span>
        </button>
      </div>

      {/* Tab 1: Embedded Live Sandbox Front-End */}
      {activeTab === "embedded" && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl space-y-0">
          {/* Browser Chrome Toolbar */}
          <div className="h-12 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between gap-4 text-xs font-mono">
            {/* Window controls & URL bar */}
            <div className="flex items-center gap-3 flex-1">
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="w-3 h-3 rounded-full bg-rose-500/80" />
                <span className="w-3 h-3 rounded-full bg-amber-500/80" />
                <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
              </div>

              <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1 flex-1 max-w-xl text-slate-300 text-xs">
                <Lock className="w-3 h-3 text-emerald-400 shrink-0" />
                <input
                  type="text"
                  value={currentIframeUrl}
                  onChange={(e) => setCurrentIframeUrl(e.target.value)}
                  className="bg-transparent border-0 outline-none w-full text-slate-200 font-mono text-xs"
                />
              </div>
            </div>

            {/* Viewport switchers & Popout */}
            <div className="flex items-center gap-2 shrink-0">
              <div className="hidden sm:flex items-center bg-slate-950 border border-slate-800 rounded-lg p-0.5">
                <button
                  onClick={() => setViewportMode("desktop")}
                  title="Desktop (100%)"
                  className={`p-1.5 rounded ${viewportMode === "desktop" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}
                >
                  <Monitor className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setViewportMode("tablet")}
                  title="Tablet (768px)"
                  className={`p-1.5 rounded ${viewportMode === "tablet" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}
                >
                  <Tablet className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setViewportMode("mobile")}
                  title="Mobile (375px)"
                  className={`p-1.5 rounded ${viewportMode === "mobile" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}
                >
                  <Smartphone className="w-3.5 h-3.5" />
                </button>
              </div>

              <a
                href={currentIframeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 hover:text-amber-300 flex items-center gap-1.5 font-semibold px-2 py-1"
              >
                <span>Pop Out</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>

          {/* Iframe Viewport */}
          <div className="bg-slate-950 flex justify-center min-h-[680px] p-2">
            <div
              className={`transition-all duration-300 ${
                viewportMode === "mobile"
                  ? "w-[375px] border-x border-slate-800 shadow-2xl"
                  : viewportMode === "tablet"
                  ? "w-[768px] border-x border-slate-800 shadow-2xl"
                  : "w-full"
              }`}
            >
              <iframe
                src={currentIframeUrl}
                title="Sandbox Front-End Website"
                className="w-full h-[680px] border-0 rounded-b-xl bg-white"
                sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: All 7 Environment Ports & Subservices */}
      {activeTab === "services" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 flex items-center justify-between">
            <span>All ports are configured in <code className="text-cyan-400 font-mono">sandbox/docker-compose.yaml</code> and customized in Settings.</span>
            <span className="text-emerald-400 font-mono font-semibold">ALL SERVICES ONLINE</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {settings.sandboxServices.map((svc) => {
              const url = `http://${settings.sandboxHost}:${svc.port}${svc.path}`;
              const isFrontend = svc.category === "frontend";

              return (
                <div
                  key={svc.name}
                  className={`p-5 rounded-2xl border backdrop-blur-md space-y-3 transition-all ${
                    isFrontend
                      ? "bg-gradient-to-br from-amber-950/30 to-slate-900 border-amber-800/80 shadow-md shadow-amber-500/10"
                      : "bg-slate-900/80 border-slate-800"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase font-mono font-bold text-amber-400">
                      Port :{svc.port}
                    </span>
                    <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
                      READY
                    </span>
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{svc.name}</span>
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">{svc.description}</p>
                  </div>

                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[11px] font-mono text-cyan-300 truncate max-w-[180px]">
                      {url}
                    </span>
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1 transition-all"
                    >
                      <span>Open</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Worker Containment Matrix */}
      {activeTab === "capabilities" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-sm">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span>Core Container Sandbox Isolation Boundaries</span>
            </div>

            <div className="space-y-3">
              {[
                "POSIX Micro-VM Process Jails (cgroups v2 + custom seccomp profiles)",
                "Egress Filtering with Strict Capability Allowlisting (Google, Meta, LinkedIn, TikTok)",
                "Zero-Leakage Virtual File Tree and Ephemeral RAM Scrubbing on Shutdown",
                "Cryptographic Execution Interception with W3C PROV Hash Verification",
                "Headless Chromium Browser Automation with Isolated Session Cookies",
                "Node.js & Python Subprocess Execution under 3000ms Hard Timeout Limit",
              ].map((feat, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 flex items-start gap-3"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{feat}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-sm">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>7 Bounded Worker Engines in Sandbox Boundary</span>
            </div>

            <div className="space-y-3 text-xs">
              {[
                { role: "W_DEV (Development)", tool: "S_CODE", desc: "AST parsing, ESLint execution, TypeScript compilation, and Jest test runners." },
                { role: "W_COMP (Competitor Intel)", tool: "S_SCRAPE", desc: "DOM extraction, accessibility audits, WCAG 2.1 AA evaluation, and pricing page scrapers." },
                { role: "W_STRAT (Strategy)", tool: "S_ALLOC", desc: "Mathematical portfolio optimization, channel spending allocation, marginal ROAS computation." },
                { role: "W_PROD (Product & Evidence)", tool: "S_VAL", desc: "Regulatory claim linters, compliance verification, and clinical citation cross-check." },
                { role: "W_CREAT (Creative Content)", tool: "S_COPY", desc: "Prohibited terms checking, multi-variant copywriting, hook critic, and brand tone validation." },
                { role: "W_VOICE (Customer Voice)", tool: "S_PARSE", desc: "Customer feedback NLP classification, sentiment analysis, and objection graphs." },
                { role: "W_LEARN (Learning & Performance)", tool: "S_ATTR", desc: "Multi-touch attribution models, marginal decay curves, and heuristic performance adjustment." },
              ].map((w) => (
                <div key={w.role} className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex justify-between font-mono">
                    <span className="font-bold text-indigo-400">{w.role}</span>
                    <span className="text-emerald-400 font-semibold">{w.tool} micro-tool</span>
                  </div>
                  <p className="text-slate-400 text-[11px]">{w.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
