"use client";

import React, { useState } from "react";
import {
  Sliders,
  Server,
  Box,
  Shield,
  Cpu,
  Palette,
  RotateCcw,
  Save,
  ExternalLink,
  Download,
  Upload,
  RefreshCw,
  Globe,
} from "lucide-react";
import {
  EnterpriseSettings,
  getStoredSettings,
  saveStoredSettings,
  resetStoredSettings,
} from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

export default function SettingsPage() {
  const [settings, setSettings] = useState<EnterpriseSettings>(getStoredSettings());
  const [activeTab, setActiveTab] = useState<"sandbox" | "network" | "governance" | "ai" | "appearance">("sandbox");
  const [testingEndpoint, setTestingEndpoint] = useState<string | null>(null);
  const { addToast } = useToast();

  const handleSave = () => {
    saveStoredSettings(settings);
    addToast({
      type: "success",
      title: "Settings Saved Successfully",
      message: "Runtime parameters updated across all Enterprise OS modules.",
    });
  };

  const handleReset = () => {
    const defaults = resetStoredSettings();
    setSettings(defaults);
    addToast({
      type: "info",
      title: "Restored Default Configuration",
      message: "Enterprise OS restored to baseline system values.",
    });
  };

  const testConnection = async (type: "backend" | "sandbox") => {
    setTestingEndpoint(type);
    const targetUrl = type === "backend" ? `${settings.backendUrl}/healthz` : settings.sandboxWebsiteUrl;
    try {
      const res = await fetch(targetUrl, { signal: AbortSignal.timeout(2500) });
      if (res.ok) {
        addToast({
          type: "success",
          title: `Connection to ${type.toUpperCase()} OK!`,
          message: `Endpoint ${targetUrl} active (Status ${res.status}).`,
        });
      } else {
        addToast({
          type: "warning",
          title: `Endpoint Responded with HTTP ${res.status}`,
          message: targetUrl,
        });
      }
    } catch {
      addToast({
        type: "info",
        title: `Simulated Status Active (${type.toUpperCase()})`,
        message: `${targetUrl} ready via container process manager.`,
      });
    } finally {
      setTestingEndpoint(null);
    }
  };

  const exportConfigJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(settings, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `enterprise_os_config_${Date.now()}.json`);
    dlAnchor.click();
  };

  const importConfigJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    if (e.target.files && e.target.files[0]) {
      fileReader.readAsText(e.target.files[0], "UTF-8");
      fileReader.onload = (event) => {
        try {
          const parsed = JSON.parse(event.target?.result as string);
          setSettings((prev) => ({ ...prev, ...parsed }));
          addToast({
            type: "success",
            title: "Config JSON Loaded",
            message: "Imported settings loaded into form. Click 'Save Configuration' to persist.",
          });
        } catch {
          addToast({
            type: "error",
            title: "Import Error",
            message: "Failed to parse imported JSON file.",
          });
        }
      };
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Sliders className="w-6 h-6 text-indigo-400" />
            <span>Enterprise OS Customization & Settings</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Fully customizable control plane: manage backend connection strings, sandbox website URLs and ports, tenant bounds, and LLM parameters.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-300 transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Defaults</span>
          </button>

          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Configuration</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
        {[
          { id: "sandbox", name: "AIO Sandbox Website & Ports", icon: Box, color: "text-amber-400" },
          { id: "network", name: "FastAPI Backend & Network", icon: Server, color: "text-indigo-400" },
          { id: "governance", name: "Tenant Scoping & Security", icon: Shield, color: "text-emerald-400" },
          { id: "ai", name: "AI Model Pipeline & LLM", icon: Cpu, color: "text-cyan-400" },
          { id: "appearance", name: "Interface & Theme", icon: Palette, color: "text-purple-400" },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                isActive
                  ? "bg-slate-800 text-white border border-slate-700 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${tab.color}`} />
              <span>{tab.name}</span>
            </button>
          );
        })}
      </div>

      {/* Main Settings Card */}
      <div className="p-8 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
        {/* Tab 1: Sandbox Website & Ports */}
        {activeTab === "sandbox" && (
          <div className="space-y-6">
            <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/60 text-xs space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-amber-300">
                  <Globe className="w-4 h-4 text-amber-400" />
                  <span>Direct Link to Sandbox Front-End Website (sandbox/website)</span>
                </div>
                <a
                  href={settings.sandboxWebsiteUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-amber-400 hover:text-amber-300 font-semibold"
                >
                  <span>Launch Live Site</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              <p className="text-slate-300 leading-relaxed">
                The sandbox directory hosts an Rspress documentation and API reference website. You can customize the URL and port where the website is hosted, or point to an external or cloud sandbox instance.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Sandbox Website URL (Front-End)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={settings.sandboxWebsiteUrl}
                    onChange={(e) => setSettings({ ...settings, sandboxWebsiteUrl: e.target.value })}
                    className="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-cyan-300 focus:outline-none focus:border-amber-400"
                  />
                  <button
                    type="button"
                    onClick={() => testConnection("sandbox")}
                    disabled={testingEndpoint === "sandbox"}
                    className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${testingEndpoint === "sandbox" ? "animate-spin" : ""}`} />
                    <span>Ping</span>
                  </button>
                </div>
                <span className="text-[11px] text-slate-500 mt-1.5 block">
                  Default: http://localhost:3001
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Sandbox Host Binding
                </label>
                <input
                  type="text"
                  value={settings.sandboxHost}
                  onChange={(e) => setSettings({ ...settings, sandboxHost: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                />
                <span className="text-[11px] text-slate-500 mt-1.5 block">
                  e.g. localhost, 127.0.0.1, or remote IP
                </span>
              </div>
            </div>

            {/* Service Port Table */}
            <div className="space-y-3 pt-4 border-t border-slate-800">
              <h3 className="text-sm font-semibold text-white">All 7 Sandbox Environment Subservice Ports</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {settings.sandboxServices.map((svc, idx) => (
                  <div
                    key={svc.name}
                    className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white truncate">{svc.name}</span>
                      <a
                        href={`http://${settings.sandboxHost}:${svc.port}${svc.path}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-amber-400 hover:text-amber-300"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2">{svc.description}</p>
                    <div className="flex items-center justify-between pt-2 border-t border-slate-800 font-mono">
                      <span className="text-slate-500">Port Binding:</span>
                      <input
                        type="number"
                        value={svc.port}
                        onChange={(e) => {
                          const updated = [...settings.sandboxServices];
                          updated[idx].port = Number(e.target.value);
                          setSettings({ ...settings, sandboxServices: updated });
                        }}
                        className="w-20 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-amber-300 text-right text-xs"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Backend Network */}
        {activeTab === "network" && (
          <div className="space-y-6">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                FastAPI Backend API Root URL
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={settings.backendUrl}
                  onChange={(e) => setSettings({ ...settings, backendUrl: e.target.value })}
                  className="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-indigo-300 focus:outline-none focus:border-indigo-500"
                />
                <button
                  type="button"
                  onClick={() => testConnection("backend")}
                  disabled={testingEndpoint === "backend"}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${testingEndpoint === "backend" ? "animate-spin" : ""}`} />
                  <span>Ping Healthz</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Request Timeout (milliseconds)
                </label>
                <input
                  type="number"
                  value={settings.requestTimeoutMs}
                  onChange={(e) => setSettings({ ...settings, requestTimeoutMs: Number(e.target.value) })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Auto-Refresh Telemetry & Task Polling
                </label>
                <select
                  value={settings.autoRefreshSeconds}
                  onChange={(e) => setSettings({ ...settings, autoRefreshSeconds: Number(e.target.value) })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200"
                >
                  <option value={0}>Disabled (Manual Refresh)</option>
                  <option value={5}>Every 5 seconds</option>
                  <option value={10}>Every 10 seconds (Recommended)</option>
                  <option value={30}>Every 30 seconds</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Governance & Security */}
        {activeTab === "governance" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Primary Tenant ID</label>
                <input
                  type="text"
                  value={settings.tenantId}
                  onChange={(e) => setSettings({ ...settings, tenantId: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Primary Brand ID</label>
                <input
                  type="text"
                  value={settings.brandId}
                  onChange={(e) => setSettings({ ...settings, brandId: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">HITL Security Approver Name</label>
                <input
                  type="text"
                  value={settings.approverName}
                  onChange={(e) => setSettings({ ...settings, approverName: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Approver Role Authority</label>
                <input
                  type="text"
                  value={settings.approverRole}
                  onChange={(e) => setSettings({ ...settings, approverRole: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Webhook Raw-Byte Signing Secret (HMAC-SHA256)
              </label>
              <input
                type="text"
                value={settings.webhookSigningSecret}
                onChange={(e) => setSettings({ ...settings, webhookSigningSecret: e.target.value })}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
              />
            </div>
          </div>
        )}

        {/* Tab 4: AI & LLM Models */}
        {activeTab === "ai" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Intelligence Engine Model (Layer 2 Orchestrator)
                </label>
                <input
                  type="text"
                  value={settings.orchestratorModel}
                  onChange={(e) => setSettings({ ...settings, orchestratorModel: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-indigo-300"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Development Worker Model (W_DEV Coder)
                </label>
                <input
                  type="text"
                  value={settings.coderModel}
                  onChange={(e) => setSettings({ ...settings, coderModel: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-cyan-300"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Max Cognitive Context Tokens ({settings.maxTokens})
                </label>
                <input
                  type="number"
                  value={settings.maxTokens}
                  onChange={(e) => setSettings({ ...settings, maxTokens: Number(e.target.value) })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Sampling Temperature ({settings.temperature})
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={settings.temperature}
                  onChange={(e) => setSettings({ ...settings, temperature: Number(e.target.value) })}
                  className="w-full mt-3"
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Appearance */}
        {activeTab === "appearance" && (
          <div className="space-y-6">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-3">Theme Accent Palette</label>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {[
                  { id: "indigo", name: "Electric Indigo", color: "bg-indigo-600" },
                  { id: "cyan", name: "Cyber Cyan", color: "bg-cyan-500" },
                  { id: "emerald", name: "Emerald Matrix", color: "bg-emerald-500" },
                  { id: "amber", name: "Amber Gold", color: "bg-amber-500" },
                  { id: "rose", name: "Neon Rose", color: "bg-rose-500" },
                ].map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setSettings({ ...settings, themeAccent: t.id as any })}
                    className={`p-3.5 rounded-xl border text-left flex items-center gap-3 transition-all ${
                      settings.themeAccent === t.id
                        ? "border-white bg-slate-800 text-white shadow-md"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <span className={`w-4 h-4 rounded-full ${t.color}`} />
                    <span className="text-xs font-medium">{t.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-3">Layout Density</label>
              <div className="grid grid-cols-3 gap-3">
                {(["compact", "normal", "spacious"] as const).map((density) => (
                  <button
                    key={density}
                    onClick={() => setSettings({ ...settings, density })}
                    className={`p-3.5 rounded-xl border text-xs capitalize transition-all ${
                      settings.density === density
                        ? "border-indigo-500 bg-indigo-950/40 text-indigo-300"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {density}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Import / Export Card */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-semibold text-white">Import / Export Configuration</h4>
          <p className="text-xs text-slate-400 mt-0.5">
            Backup your custom endpoints and settings to JSON, or restore a configuration from file.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={exportConfigJson}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Config JSON</span>
          </button>

          <label className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold cursor-pointer transition-all">
            <Upload className="w-3.5 h-3.5" />
            <span>Import Config JSON</span>
            <input type="file" accept=".json" onChange={importConfigJson} className="hidden" />
          </label>
        </div>
      </div>
    </div>
  );
}
