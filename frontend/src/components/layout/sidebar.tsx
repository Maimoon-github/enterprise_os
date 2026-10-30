"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard" },
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
    <aside className="w-64 bg-slate-900 border-r border-slate-800 p-6 flex flex-col justify-between shrink-0">
      <div>
        <div className="flex items-center gap-2 mb-8">
          <div className="h-6 w-6 rounded bg-indigo-600 flex items-center justify-center font-bold text-xs text-white">
            AG
          </div>
          <span className="font-semibold tracking-wide text-sm text-white">Marketing OS</span>
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 rounded-lg text-sm transition ${
                  isActive
                    ? "bg-slate-800 text-white font-medium"
                    : "text-slate-300 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="pt-4 border-t border-slate-800 text-xs text-slate-500">
        Self-Hosted • FastAPI + LangGraph
      </div>
    </aside>
  );
}
