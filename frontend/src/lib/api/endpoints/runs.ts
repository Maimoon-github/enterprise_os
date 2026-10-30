import { apiClient } from "../client";
import { RunResponse, RunCreate } from "@marketing-os/contracts";

export const runsApi = {
  dispatch: (data: RunCreate) =>
    apiClient<RunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  get: (runId: string) => apiClient<RunResponse>(`/runs/${runId}`),
  list: (campaignId?: string) =>
    apiClient<RunResponse[]>(campaignId ? `/runs?campaign_id=${campaignId}` : "/runs"),
};
