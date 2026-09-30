"use client";

import React from "react";
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
  Cpu,
  Layers,
  Box,
} from "lucide-react";

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
    badge: "LLM",
    badgeColor: "bg-indigo-950 text-indigo-400 border-indigo-800",
  },
  {
    name: "HITL Approvals",
    href: "/approvals",
    icon: CheckSquare,
    badge: "2 Pending",
    badgeColor: "bg-amber-950 text-amber-400 border-amber-800",
  },
  {
    name: "CTS State Machine",
    href: "/tasks",
    icon: Kanban,
  },
  {
    name: "AIO Sandbox Portal",
    href: "/sandbox",
    icon: Box,
    badge: "Live :3001",
    badgeColor: "bg-amber-950 text-amber-400 border-amber-800",
  },
  {
    name: "Bounded Workers",
    href: "/workers",
    icon: Bot,
    badge: "7 Agents",
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
  },
];

export const Sidebar = () => {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-slate-800/80 bg-slate-950/60 backdrop-blur-md flex flex-col justify-between p-4 shrink-0 min-h-[calc(100vh-4rem)]">
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
                      ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 shadow-sm shadow-indigo-500/10"
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

        {/* Runtime Environment Info */}
        <div className="pt-4 border-t border-slate-800/60">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider px-3 mb-2">
            Runtime Isolation
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span>Sandbox Status</span>
              <span className="text-emerald-400 font-mono font-medium">ISOLATED</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span>CTS Protocol</span>
              <span className="text-cyan-400 font-mono font-medium">v1.0.0</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span>LLM Engine</span>
              <span className="text-indigo-400 font-mono font-medium">Qwen 2.5 7B</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-900/40 text-xs text-indigo-300/80">
        <div className="font-semibold text-indigo-200 mb-0.5">Enterprise OS Node</div>
        <p className="text-[11px] leading-relaxed text-indigo-300/70">
          Multi-Agent Autonomous Execution with Strict Human-In-The-Loop Signoff
        </p>
      </div>
    </aside>
  );
};
