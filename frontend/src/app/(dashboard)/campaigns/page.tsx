"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useCampaigns } from "@/hooks/use-campaigns";

export default function CampaignsPage() {
  const { campaigns, fetchCampaigns, loading } = useCampaigns();

  useEffect(() => {
    fetchCampaigns().catch(() => {});
  }, [fetchCampaigns]);

  const displayCampaigns = campaigns.length > 0 ? campaigns : [
    {
      id: "c1",
      name: "Q4 Autonomous Platform Launch",
      brand_id: "apex-horizon",
      status: "review",
      blueprint: { target_platforms: ["linkedin", "x", "instagram", "threads"] },
    },
    {
      id: "c2",
      name: "B2B Thought Leadership Series",
      brand_id: "apex-horizon",
      status: "published",
      blueprint: { target_platforms: ["linkedin", "x"] },
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Campaign Blueprints</h1>
          <p className="text-slate-400 text-sm">Design, inspect, and execute multi-channel marketing campaigns.</p>
        </div>
        <Link
          href="/campaigns/new"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          New Campaign
        </Link>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-xs uppercase font-mono">
            <tr>
              <th className="px-6 py-3">Campaign Name</th>
              <th className="px-6 py-3">Brand Workspace</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Target Platforms</th>
              <th className="px-6 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading && campaigns.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-xs text-slate-500">
                  Loading campaigns from database...
                </td>
              </tr>
            ) : (
              displayCampaigns.map((camp: any) => {
                const platformsCount = camp.blueprint?.target_platforms?.length || 4;
                return (
                  <tr key={camp.id} className="hover:bg-slate-800/50">
                    <td className="px-6 py-4 font-medium text-white">{camp.name}</td>
                    <td className="px-6 py-4 text-slate-400 text-xs font-mono">
                      {camp.brand_id ? String(camp.brand_id).slice(0, 12) : "Apex Horizon"}
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 text-xs rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 capitalize font-mono">
                        {camp.status || "draft"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-xs">
                      {platformsCount} Platform(s)
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link
                        href={`/campaigns/${camp.id}`}
                        className="text-indigo-400 hover:text-indigo-300 text-xs font-semibold"
                      >
                        Inspect Blueprint →
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
