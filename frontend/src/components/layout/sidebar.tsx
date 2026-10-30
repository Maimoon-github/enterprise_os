"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Orchestrator Chat", href: "/chat" },
  { label: "Campaigns", href: "/campaigns" },
  { label: "Approvals (HITL)", href: "/approvals" },
  { label: "Agents & Fleet", href: "/agents" },
  { label: "Skills (SKILL.md)", href: "/skills" },
  { label: "MCP Servers", href: "/mcp-servers" },
  { label: "Media Studio", href: "/media" },
  { label: "Analytics", href: "/analytics" },
  { label: "Schedules", href: "/schedules" },
  { label: "Brand Workspaces", href: "/brands" },
  { label: "Observability", href: "/observability" },
  { label: "Settings", href: "/settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 glass-panel border-r border-glass-subtle p-6 flex flex-col justify-between shrink-0">
      <div>
        <div className="flex items-center gap-2.5 mb-8">
          <div className="h-7 w-7 rounded-lg bg-bloodstone-crimson border border-rose-500/30 flex items-center justify-center font-bold text-xs text-bloodstone-text shadow-crimson-glow">
            AG
          </div>
          <span className="font-semibold tracking-wide text-sm text-bloodstone-text">Marketing OS</span>
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 rounded-lg text-sm transition-all duration-normal ease-out-expo ${
                  isActive
                    ? "bg-glass-emerald border border-glass-specular text-bloodstone-mint shadow-bloodstone-glow font-medium"
                    : "text-bloodstone-text-muted hover:text-bloodstone-text hover:bg-glass-base"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="pt-4 border-t border-glass-dark text-xs text-bloodstone-text-dim">
        Self-Hosted • FastAPI + LangGraph
      </div>
    </aside>
  );
}
