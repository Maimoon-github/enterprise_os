import { apiClient } from "../client";
import { CrossPlatformKPIs, AnomalyAlert, AnalyticsChannelState } from "@marketing-os/contracts";

export const analyticsApi = {
  getKPIs: () => apiClient<CrossPlatformKPIs>("/analytics/kpis"),
  getAnomalies: () => apiClient<AnomalyAlert[]>("/analytics/anomalies"),
  getChannels: () => apiClient<AnalyticsChannelState[]>("/analytics/channels"),
};
