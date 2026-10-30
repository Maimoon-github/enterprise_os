"use client";

import { useEffect, useState } from "react";
import { settingsApi } from "@/lib/api/endpoints/settings";
import {
  SettingsResponse,
  PlatformConnectionResponse,
  UserPreferencesResponse,
} from "@marketing-os/contracts";

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [platforms, setPlatforms] = useState<PlatformConnectionResponse[]>([]);
  const [preferences, setPreferences] = useState<UserPreferencesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Configuration modal state
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [accountName, setAccountName] = useState("");
  const [testResult, setTestResult] = useState<{ is_valid: boolean; message: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, p, pref] = await Promise.all([
        settingsApi.getSettings(),
        settingsApi.listPlatforms(),
        settingsApi.getPreferences(),
      ]);
      setSettings(s);
      setPlatforms(p);
      setPreferences(pref);
    } catch {
      // Fallback defaults
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenConfig = (p: PlatformConnectionResponse) => {
    setSelectedPlatform(p.platform);
    setAccountName(p.account_name || "");
    setClientId("");
    setClientSecret("");
    setAccessToken("");
    setTestResult(null);
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlatform) return;
    setIsSubmitting(true);
    try {
      await settingsApi.configurePlatform(selectedPlatform, {
        client_id: clientId || undefined,
        client_secret: clientSecret || undefined,
        access_token: accessToken || undefined,
        account_name: accountName || undefined,
      });
      await loadData();
      setSelectedPlatform(null);
    } catch (err: any) {
      alert("Failed to save credentials: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTestConnection = async (platformName: string) => {
    try {
      const res = await settingsApi.testPlatform(platformName);
      setTestResult({ is_valid: res.is_valid, message: res.message });
    } catch (err: any) {
      setTestResult({ is_valid: false, message: err.message });
    }
  };

  const handleDisconnect = async (platformName: string) => {
    if (!confirm(`Disconnect ${platformName} and purge encrypted secrets?`)) return;
    try {
      await settingsApi.disconnectPlatform(platformName);
      await loadData();
    } catch {}
  };

  const limits: Record<string, string> = {
    memory_limit: String(settings?.sandbox_limits?.memory_limit || "512m"),
    cpu_limit: String(settings?.sandbox_limits?.cpu_limit || "1.0"),
    network_default: String(settings?.sandbox_limits?.network_default || "none"),
    security_opt: String(settings?.sandbox_limits?.security_opt || "no-new-privileges"),
    cap_drop: String(settings?.sandbox_limits?.cap_drop || "ALL"),
    mount_mode: String(settings?.sandbox_limits?.mount_mode || "ro"),
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
        <h1 className="text-2xl font-bold tracking-tight text-bloodstone-text">
          Control Plane Configuration & Platform Integrations
        </h1>
        <p className="text-bloodstone-text-muted text-sm">
          Zero-trust platform credentials, rootless Podman sandboxes, and Celery asynchronous task queues.
        </p>
      </div>

      {/* Target Platforms Integration Grid */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-bloodstone-text">Social Platform Integrations</h3>
            <p className="text-xs text-bloodstone-text-muted">
              Credentials encrypted with zero-trust AES-256-GCM. Plaintext is never logged or exposed.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-glass-emerald border border-glass-specular text-bloodstone-mint shadow-bloodstone-glow">
            {platforms.filter((p) => p.is_connected).length} / 8 Active
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {platforms.map((p) => (
            <div
              key={p.platform}
              className="p-3.5 glass-panel rounded-xl flex items-center justify-between transition-all"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-bloodstone-text capitalize">{p.platform}</span>
                  {p.is_connected ? (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-glass-emerald text-bloodstone-mint border border-glass-specular font-mono">
                      Connected
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-glass-base text-bloodstone-text-dim border border-glass-subtle font-mono">
                      Unlinked
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-bloodstone-text-dim">
                  {p.is_connected
                    ? `${p.account_name || "Account"} (${p.masked_client_id || "AES Encrypted"})`
                    : "No credentials stored"}
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleOpenConfig(p)}
                  className="px-2.5 py-1 glass-card hover:border-glass-specular text-bloodstone-text rounded-lg text-xs transition"
                >
                  Configure
                </button>
                {p.is_connected && (
                  <button
                    onClick={() => handleDisconnect(p.platform)}
                    title="Disconnect"
                    className="px-2 py-1 glass-crimson rounded-lg text-xs text-bloodstone-text transition"
                  >
                    Disconnect
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rootless Podman Sandbox Hardening */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-bloodstone-text">Rootless Podman Sandbox Hardening</h3>
            <p className="text-xs text-bloodstone-text-muted">
              Ephemeral container runtime for Tier 3 Agent Skill scripts and untrusted execution isolation.
            </p>
          </div>
          <span className="px-2.5 py-1 text-xs rounded-full bg-glass-emerald text-bloodstone-mint border border-glass-specular font-mono">
            {settings?.sandbox_engine || "rootless-podman"}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs font-mono">
          <div className="p-3 glass-panel rounded-lg space-y-1">
            <span className="text-bloodstone-text-dim text-[10px] uppercase">Memory Limit</span>
            <div className="text-bloodstone-text font-bold">{limits.memory_limit}</div>
          </div>
          <div className="p-3 glass-panel rounded-lg space-y-1">
            <span className="text-bloodstone-text-dim text-[10px] uppercase">CPU Allocation</span>
            <div className="text-bloodstone-text font-bold">{limits.cpu_limit} CPUs</div>
          </div>
          <div className="p-3 glass-panel rounded-lg space-y-1">
            <span className="text-bloodstone-text-dim text-[10px] uppercase">Network Isolation</span>
            <div className="text-bloodstone-mint font-bold">{limits.network_default}</div>
          </div>
          <div className="p-3 glass-panel rounded-lg space-y-1">
            <span className="text-bloodstone-text-dim text-[10px] uppercase">Security Opt</span>
            <div className="text-bloodstone-mint font-bold">{limits.security_opt}</div>
          </div>
          <div className="p-3 glass-panel rounded-lg space-y-1">
            <span className="text-bloodstone-text-dim text-[10px] uppercase">Linux Capabilities</span>
            <div className="text-bloodstone-mint font-bold">{limits.cap_drop}</div>
          </div>
          <div className="p-3 glass-panel rounded-lg space-y-1">
            <span className="text-bloodstone-text-dim text-[10px] uppercase">Workspace Mount</span>
            <div className="text-bloodstone-text font-bold">:{limits.mount_mode} (Read-Only)</div>
          </div>
        </div>
      </div>

      {/* Celery Task Queues */}
      <div className="glass-card p-6 space-y-4">
        <h3 className="text-base font-semibold text-bloodstone-text">Celery Asynchronous Task Queues</h3>
        <p className="text-xs text-bloodstone-text-muted">
          Redis broker with Kombu partitioned queues, W3C traceparent propagation, and late acknowledgment.
        </p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          {queues.map((q) => (
            <div
              key={q}
              className="p-3 glass-panel rounded-lg flex items-center justify-between font-mono"
            >
              <span className="text-bloodstone-mint font-semibold">{q}</span>
              <span className="text-bloodstone-text-muted text-[11px] font-sans">Active • acks_late</span>
            </div>
          ))}
        </div>
      </div>

      {/* Configuration Modal */}
      {selectedPlatform && (
        <div className="fixed inset-0 bg-bloodstone-canvas/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <div className="glass-panel-elevated rounded-xl p-6 max-w-lg w-full space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-bloodstone-text capitalize">
                Configure {selectedPlatform} Credentials
              </h3>
              <button
                onClick={() => setSelectedPlatform(null)}
                className="text-bloodstone-text-dim hover:text-bloodstone-text"
              >
                ✕
              </button>
            </div>

            <div className="p-3 glass-panel rounded-lg text-[11px] text-bloodstone-text-muted flex items-start gap-2">
              <span className="text-bloodstone-mint">🔒</span>
              <span>
                Zero-Trust Storage: All client credentials and OAuth secrets are encrypted via AES-256-GCM.
                Raw tokens are never returned to the UI or LLM workers.
              </span>
            </div>

            <form onSubmit={handleSaveConfig} className="space-y-3 text-xs">
              <div>
                <label className="block text-bloodstone-text-muted mb-1 font-semibold uppercase text-[10px]">
                  Account / Organization Name
                </label>
                <input
                  type="text"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                  placeholder="e.g. Apex Marketing HQ"
                  className="w-full glass-input px-3 py-2 text-bloodstone-text"
                />
              </div>

              <div>
                <label className="block text-bloodstone-text-muted mb-1 font-semibold uppercase text-[10px]">
                  Client ID / App Key
                </label>
                <input
                  type="text"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="Platform App ID"
                  className="w-full glass-input px-3 py-2 text-bloodstone-text"
                />
              </div>

              <div>
                <label className="block text-bloodstone-text-muted mb-1 font-semibold uppercase text-[10px]">
                  Client Secret
                </label>
                <input
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="w-full glass-input px-3 py-2 text-bloodstone-text"
                />
              </div>

              <div>
                <label className="block text-bloodstone-text-muted mb-1 font-semibold uppercase text-[10px]">
                  Access / Bearer Token
                </label>
                <input
                  type="password"
                  value={accessToken}
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="w-full glass-input px-3 py-2 text-bloodstone-text"
                />
              </div>

              {testResult && (
                <div
                  className={`p-3 rounded-lg text-xs font-mono ${
                    testResult.is_valid
                      ? "bg-glass-emerald border border-glass-specular text-bloodstone-mint"
                      : "bg-glass-crimson border border-bloodstone-crimson text-bloodstone-text"
                  }`}
                >
                  {testResult.message}
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => handleTestConnection(selectedPlatform)}
                  className="px-3.5 py-1.5 glass-card text-bloodstone-text text-xs rounded-lg font-medium transition"
                >
                  Test Decryption Harness
                </button>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedPlatform(null)}
                    className="px-3.5 py-1.5 text-bloodstone-text-muted hover:text-bloodstone-text text-xs rounded-lg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-1.5 glass-emerald text-bloodstone-text text-xs rounded-lg font-semibold transition"
                  >
                    {isSubmitting ? "Encrypting..." : "Save Encrypted"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
