export default function MCPServersPage() {
  const servers = [
    { name: "BrandRAGServer", transport: "Streamable HTTP (:8081)", tools: 3, resources: 2, status: "Connected" },
    { name: "SocialGatewayServer", transport: "Streamable HTTP (:8082)", tools: 8, resources: 2, status: "Connected" },
    { name: "MediaStudioServer", transport: "Streamable HTTP (:8083)", tools: 4, resources: 1, status: "Connected" },
    { name: "AnalyticsServer", transport: "Streamable HTTP (:8084)", tools: 3, resources: 2, status: "Connected" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Model Context Protocol (MCP) Servers</h1>
        <p className="text-slate-400 text-sm">FastMCP capability servers adhering to the MCP 2026-07-28 specification.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {servers.map((srv) => (
          <div key={srv.name} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white text-base">{srv.name}</h3>
              <span className="text-xs text-emerald-400 font-semibold">{srv.status}</span>
            </div>
            <div className="text-xs text-slate-400 font-mono">{srv.transport}</div>
            <div className="flex gap-4 text-xs text-slate-300 pt-2 border-t border-slate-800">
              <div>Tools: <span className="font-semibold text-white">{srv.tools}</span></div>
              <div>Resources: <span className="font-semibold text-white">{srv.resources}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
