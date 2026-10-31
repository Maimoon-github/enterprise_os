"use client";

import { useEffect, useState } from "react";
import { useCampaigns } from "@/hooks/use-campaigns";
import { useApprovals } from "@/hooks/use-approvals";
import { settingsApi } from "@/lib/api/endpoints/settings";

export default function DashboardOverviewPage() {
  const { campaigns, fetchCampaigns } = useCampaigns();
  const { approvals, fetchApprovals } = useApprovals();
  const [connectedPlatforms, setConnectedPlatforms] = useState<number>(0);
  const [totalPlatforms, setTotalPlatforms] = useState<number>(8);

  useEffect(() => {
    fetchCampaigns().catch(() => {});
    fetchApprovals().catch(() => {});
    settingsApi
      .listPlatforms()
      .then((platforms) => {
        setTotalPlatforms(platforms.length);
        setConnectedPlatforms(platforms.filter((p) => p.is_connected).length);
      })
      .catch(() => {});
  }, [fetchCampaigns, fetchApprovals]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-bloodstone-text">Executive Control Plane</h1>
        <p className="text-bloodstone-text-muted text-sm">Real-time status of multi-agent marketing operations and platform health.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-text-muted">Active Campaigns</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-text">{campaigns.length}</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-mint">Pending Approvals</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-mint">{approvals.length}</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-text-muted">Platforms Connected</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-text">{connectedPlatforms} / {totalPlatforms}</p>
        </div>
        <div className="glass-card p-5">
          <span className="text-xs font-semibold uppercase text-bloodstone-text-muted">Approval Invariant</span>
          <p className="text-2xl font-bold mt-2 text-bloodstone-mint">Human Gate Active</p>
        </div>
      </div>
    </div>
  );
}
