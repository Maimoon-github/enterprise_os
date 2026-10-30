"use client";

import { useCallback, useState } from "react";
import { campaignsApi } from "@/lib/api/endpoints/campaigns";
import { CampaignCreate, CampaignResponse, CampaignUpdate } from "@marketing-os/contracts";
import { apiClient } from "@/lib/api/client";

export function useCampaigns() {
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignResponse[]>([]);

  const fetchCampaigns = useCallback(async (brandId?: string) => {
    setLoading(true);
    try {
      const url = brandId ? `/campaigns?brand_id=${brandId}` : "/campaigns";
      const data = await apiClient<CampaignResponse[]>(url);
      setCampaigns(data);
      return data;
    } finally {
      setLoading(false);
    }
  }, []);

  const createCampaign = async (payload: CampaignCreate) => {
    setLoading(true);
    try {
      const created = await campaignsApi.create(payload);
      setCampaigns((prev) => [created, ...prev]);
      return created;
    } finally {
      setLoading(false);
    }
  };

  const updateCampaign = async (id: string, payload: CampaignUpdate) => {
    setLoading(true);
    try {
      const updated = await apiClient<CampaignResponse>(`/campaigns/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setCampaigns((prev) => prev.map((c) => (c.id === id ? updated : c)));
      return updated;
    } finally {
      setLoading(false);
    }
  };

  return { campaigns, fetchCampaigns, createCampaign, updateCampaign, loading };
}
