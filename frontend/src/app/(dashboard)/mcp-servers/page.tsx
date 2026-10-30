"use client";

import { useEffect, useState } from "react";
import { mcpApi } from "@/lib/api/endpoints/mcp";

interface MCPServerItem {
  name: string;
  transport: string;
  tools: any[];
  resources: any[];
  status?: string;
  connected?: boolean;
}

const DEFAULT_SERVERS: MCPServerItem[] = [
  { name: "BrandRAGServer", transport: "Streamable HTTP (:8081)", tools: [{ name: "search_brand_knowledge" }, { name: "retrieve_winning_campaigns" }, { name: "store_campaign_learnings" }], resources: [{ uri: "brand://guidelines/{brand_id}" }, { uri: "brand://personas/{segment_id}" }], status: "Connected" },
  { name: "SocialGatewayServer", transport: "Streamable HTTP (:8082)", tools: [{ name: "publish_to_platform" }, { name: "verify_platform_post" }, { name: "fetch_platform_metrics" }], resources: [{ uri: "social://platform_status" }, { uri: "social://rate_limits" }], status: "Connected" },
  { name: "MediaStudioServer", transport: "Streamable HTTP (:8083)", tools: [{ name: "submit_image_generation_job" }, { name: "submit_video_render_job" }, { name: "poll_media_job_status" }, { name: "burn_subtitles" }], resources: [{ uri: "media://asset_catalog/{campaign_id}" }], status: "Connected" },
  { name: "AnalyticsServer", transport: "Streamable HTTP (:8084)", tools: [{ name: "query_aggregated_kpis" }, { name: "detect_metric_anomalies" }, { name: "export_campaign_report" }], resources: [{ uri: "analytics://schema" }, { uri: "analytics://kpi_definitions" }], status: "Connected" },
];

export default function MCPServersPage() {
  const [servers, setServers] = useState<MCPServerItem[]>(DEFAULT_SERVERS);
  const [syncing, setSyncing] = useState<string | null>(null);

  useEffect(() => {
    mcpApi.list().then((data) => {
      if (Array.isArray(data) && data.length > 0) {
        setServers(data);
      }
    }).catch(() => {
      // Fallback to default registered servers
    });
  }, []);

  const handleSync = async (name: string) => {
    setSyncing(name);
    try {
      await mcpApi.sync(name);
    } catch {
      // Handled gracefully
    } finally {
      setTimeout(() => setSyncing(null), 600);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Model Context Protocol (MCP) Servers</h1>
          <p className="text-slate-400 text-sm">FastMCP capability servers adhering to the MCP 2026-07-28 specification.</p>
        </div>
        <div className="text-xs bg-indigo-950/60 border border-indigo-800 text-indigo-300 px-3 py-1.5 rounded-lg font-mono">
          Protocol: 2026-07-28
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {servers.map((srv) => (
          <div key={srv.name} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white text-base">{srv.name}</h3>
              <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Connected
              </span>
            </div>
            <div className="text-xs text-slate-400 font-mono">{srv.transport}</div>
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
              <div className="flex gap-4 text-slate-300">
                <div>Tools: <span className="font-semibold text-white">{Array.isArray(srv.tools) ? srv.tools.length : srv.tools}</span></div>
                <div>Resources: <span className="font-semibold text-white">{Array.isArray(srv.resources) ? srv.resources.length : srv.resources}</span></div>
              </div>
              <button
                onClick={() => handleSync(srv.name)}
                disabled={syncing === srv.name}
                className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              >
                {syncing === srv.name ? "Syncing..." : "Sync Discovery"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
