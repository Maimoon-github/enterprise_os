"use client";

import { useState } from "react";
import { campaignsApi } from "@/lib/api/endpoints/campaigns";
import { CampaignCreate } from "@marketing-os/contracts";

export function useCampaigns() {
  const [loading, setLoading] = useState(false);

  const createCampaign = async (payload: CampaignCreate) => {
    setLoading(true);
    try {
      return await campaignsApi.create(payload);
    } finally {
      setLoading(false);
    }
  };

  return { createCampaign, loading };
}
