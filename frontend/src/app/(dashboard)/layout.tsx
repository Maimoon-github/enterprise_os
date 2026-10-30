import Link from "next/link";

const NAV_ITEMS = [
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

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 bg-slate-900 border-r border-slate-800 p-6 flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-2 mb-8">
            <div className="h-6 w-6 rounded bg-indigo-600 flex items-center justify-center font-bold text-xs">AG</div>
            <span className="font-semibold tracking-wide text-sm">Marketing OS</span>
          </div>
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-slate-800 transition"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="pt-4 border-t border-slate-800 text-xs text-slate-500">
          Self-Hosted • FastAPI + LangGraph
        </div>
      </aside>
      <main className="flex-1 p-8 overflow-y-auto">{children}</main>
    </div>
  );
}
