"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  CheckSquare,
  Kanban,
  Bot,
  ScrollText,
  Activity,
  Box,
  Sliders,
  ExternalLink,
} from "lucide-react";
import { getStoredSettings, subscribeSettings, EnterpriseSettings } from "@/lib/settings";

interface NavItem {
  name: string;
  href: string;
  icon: React.ElementType;
  badge?: string;
  badgeColor?: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    name: "Mission Control",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    name: "Directives & DAG",
    href: "/directives",
    icon: GitBranch,
    badge: "1-Click DAG",
    badgeColor: "bg-indigo-950 text-indigo-400 border-indigo-800",
  },
  {
    name: "HITL Approvals",
    href: "/approvals",
    icon: CheckSquare,
    badge: "Cryptographic",
    badgeColor: "bg-amber-950 text-amber-400 border-amber-800",
  },
  {
    name: "CTS State Machine",
    href: "/tasks",
    icon: Kanban,
    badge: "v1.0",
    badgeColor: "bg-cyan-950 text-cyan-400 border-cyan-800",
  },
  {
    name: "AIO Sandbox Portal",
    href: "/sandbox",
    icon: Box,
    badge: "Synced :3001",
    badgeColor: "bg-amber-950 text-amber-400 border-amber-800",
  },
  {
    name: "Bounded Workers",
    href: "/workers",
    icon: Bot,
    badge: "7 Engines",
    badgeColor: "bg-emerald-950 text-emerald-400 border-emerald-800",
  },
  {
    name: "Provenance Ledger",
    href: "/audit",
    icon: ScrollText,
    badge: "W3C PROV",
    badgeColor: "bg-cyan-950 text-cyan-400 border-cyan-800",
  },
  {
    name: "System Telemetry",
    href: "/telemetry",
    icon: Activity,
    badge: "1-Click Probe",
    badgeColor: "bg-rose-950 text-rose-400 border-rose-800",
  },
  {
    name: "Customization & Settings",
    href: "/settings",
    icon: Sliders,
    badge: "Configure",
    badgeColor: "bg-purple-950 text-purple-400 border-purple-800",
  },
];

export const Sidebar = () => {
  const pathname = usePathname();
  const [settings, setSettings] = useState<EnterpriseSettings>(getStoredSettings());

  useEffect(() => {
    return subscribeSettings((newSettings) => {
      setSettings(newSettings);
    });
  }, []);

  return (
    <aside className="w-64 border-r border-slate-800/80 bg-slate-950/70 backdrop-blur-md flex flex-col justify-between p-4 shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="space-y-6">
        {/* Navigation Category */}
        <div>
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider px-3 mb-2">
            Governance & Execution
          </div>
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 shadow-sm shadow-indigo-500/10 font-semibold"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={`w-4 h-4 ${
                        isActive ? "text-indigo-400" : "text-slate-500 group-hover:text-slate-300"
                      }`}
                    />
                    <span>{item.name}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
                        item.badgeColor || "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* PROMINENT DIRECT LINK CARD TO SANDBOX WEBSITE */}
        <div className="p-3.5 rounded-xl bg-gradient-to-br from-amber-950/40 via-slate-900 to-slate-900 border border-amber-800/60 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4 text-amber-400 animate-pulse" />
              <span className="text-xs font-bold text-amber-300">Sandbox Website</span>
            </div>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
              :3001
            </span>
          </div>

          <p className="text-[11px] text-slate-300 leading-snug">
            Direct link to Rspress documentation and API reference in <code className="text-amber-300 text-[10px]">sandbox/website</code>.
          </p>

          <a
            href={settings.sandboxWebsiteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full py-1.5 px-3 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-md shadow-amber-600/20 transition-all group"
          >
            <span>Launch Website</span>
            <ExternalLink className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
          </a>
        </div>
      </div>

      {/* Footer Info / Active Scoping */}
      <div className="pt-4 border-t border-slate-800/80 space-y-2 text-xs">
        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider px-1">
          Active Runtime Scoping
        </div>
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 font-mono text-[11px] text-slate-400 space-y-1">
          <div className="flex justify-between">
            <span>Model:</span>
            <span className="text-indigo-400 truncate max-w-[120px]">{settings.orchestratorModel}</span>
          </div>
          <div className="flex justify-between">
            <span>Risk Ceiling:</span>
            <span className="text-amber-400 uppercase">{settings.riskCeiling}</span>
          </div>
          <div className="flex justify-between">
            <span>Isolation:</span>
            <span className="text-emerald-400">Zero-Trust</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
