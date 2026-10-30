import { apiClient } from "../client";
import { CampaignResponse, CampaignCreate } from "@marketing-os/contracts";

export const campaignsApi = {
  list: () => apiClient<CampaignResponse[]>("/campaigns"),
  create: (data: CampaignCreate) =>
    apiClient<CampaignResponse>("/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
