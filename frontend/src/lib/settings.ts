/**
 * Enterprise OS Persistent Settings & Customization Store
 * Allows runtime configuration of backend endpoints, sandbox ports,
 * tenant/brand scopes, governance constraints, and UI appearance.
 */

export interface SandboxServiceConfig {
  name: string;
  port: number;
  protocol: "http" | "ws";
  path: string;
  description: string;
  category: "frontend" | "ide" | "notebook" | "remote_desktop" | "mcp" | "gateway";
  enabled: boolean;
}

export interface EnterpriseSettings {
  // Backend & Connection
  backendUrl: string;
  requestTimeoutMs: number;
  autoRefreshSeconds: number;
  simulationFallback: boolean;

  // Sandbox & Daemon
  sandboxDaemonUrl: string;
  sandboxWebsiteUrl: string;
  sandboxHost: string;
  sandboxServices: SandboxServiceConfig[];

  // Tenant & Governance Scoping
  tenantId: string;
  brandId: string;
  allowedChannels: string[];
  riskCeiling: "low" | "medium" | "high";
  defaultBudgetCap: number;

  // Security & HITL Reviewer
  approverName: string;
  approverRole: string;
  signingPublicKeyPem: string;
  webhookSigningSecret: string;

  // AI & Model Parameters
  orchestratorModel: string;
  coderModel: string;
  maxTokens: number;
  temperature: number;

  // UI & Customization
  themeAccent: "indigo" | "cyan" | "emerald" | "amber" | "rose";
  density: "compact" | "normal" | "spacious";
  soundEffects: boolean;
}

export const DEFAULT_SANDBOX_SERVICES: SandboxServiceConfig[] = [
  {
    name: "Sandbox Website (Docs & API)",
    port: 3001,
    protocol: "http",
    path: "/",
    description: "Rspress Documentation, Interactive API Reference, and System Guides (sandbox/website)",
    category: "frontend",
    enabled: true,
  },
  {
    name: "Public Container Gateway",
    port: 8080,
    protocol: "http",
    path: "/",
    description: "aio-sandbox ingress reverse proxy and container status endpoint",
    category: "gateway",
    enabled: true,
  },
  {
    name: "VS Code Web (Code Server)",
    port: 8200,
    protocol: "http",
    path: "/",
    description: "Browser-based VSCode instance with full file tree and LSP virtualization",
    category: "ide",
    enabled: true,
  },
  {
    name: "JupyterLab Notebooks",
    port: 8888,
    protocol: "http",
    path: "/lab",
    description: "Interactive Python data science kernels and model evaluation notebooks",
    category: "notebook",
    enabled: true,
  },
  {
    name: "noVNC Remote Desktop",
    port: 6080,
    protocol: "http",
    path: "/vnc.html",
    description: "Isolated graphical X11 desktop display for browser automation inspection",
    category: "remote_desktop",
    enabled: true,
  },
  {
    name: "Model Context Protocol (MCP Hub)",
    port: 8079,
    protocol: "http",
    path: "/",
    description: "Outbound tool execution router and bounded capability allowlist",
    category: "mcp",
    enabled: true,
  },
  {
    name: "Sandbox Daemon API",
    port: 8091,
    protocol: "http",
    path: "/",
    description: "Internal micro-virtualization management daemon and process controller",
    category: "gateway",
    enabled: true,
  },
];

export const DEFAULT_SETTINGS: EnterpriseSettings = {
  backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
  requestTimeoutMs: 5000,
  autoRefreshSeconds: 10,
  simulationFallback: true,

  sandboxDaemonUrl: process.env.NEXT_PUBLIC_SANDBOX_DAEMON_URL || "http://localhost:18091",
  sandboxWebsiteUrl: process.env.NEXT_PUBLIC_SANDBOX_URL || "http://localhost:3001",
  sandboxHost: "localhost",
  sandboxServices: DEFAULT_SANDBOX_SERVICES,

  tenantId: "tenant-enterprise-live",
  brandId: "brand-enterprise",
  allowedChannels: ["web", "email", "social", "ads"],
  riskCeiling: "medium",
  defaultBudgetCap: 25000,

  approverName: "SecOps Lead (Maimoon)",
  approverRole: "Security Officer",
  signingPublicKeyPem: "-----BEGIN PUBLIC KEY-----\\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...\\n-----END PUBLIC KEY-----",
  webhookSigningSecret: "whsec_test_secret_32bytes_example",

  orchestratorModel: "qwen2.5:7b",
  coderModel: "qwen2.5-coder:7b",
  maxTokens: 16384,
  temperature: 0.2,

  themeAccent: "indigo",
  density: "normal",
  soundEffects: false,
};

const STORAGE_KEY = "enterprise_os_custom_settings_v1";

type Listener = (settings: EnterpriseSettings) => void;
const listeners = new Set<Listener>();

export function getStoredSettings(): EnterpriseSettings {
  if (typeof window === "undefined") {
    return DEFAULT_SETTINGS;
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveStoredSettings(newSettings: Partial<EnterpriseSettings>): EnterpriseSettings {
  const current = getStoredSettings();
  const merged: EnterpriseSettings = { ...current, ...newSettings };
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
    } catch (e) {
      console.error("Failed to persist settings to localStorage:", e);
    }
  }
  listeners.forEach((listener) => listener(merged));
  return merged;
}

export function resetStoredSettings(): EnterpriseSettings {
  if (typeof window !== "undefined") {
    localStorage.removeItem(STORAGE_KEY);
  }
  listeners.forEach((listener) => listener(DEFAULT_SETTINGS));
  return DEFAULT_SETTINGS;
}

export function subscribeSettings(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
