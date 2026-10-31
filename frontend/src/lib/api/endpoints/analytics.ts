import { apiClient } from "../client";
import {
  CrossPlatformKPIs,
  AnomalyAlert,
  AnalyticsChannelState,
  AnalyticsOverviewResponse,
} from "@marketing-os/contracts";

export const analyticsApi = {
  getKPIs: () => apiClient<CrossPlatformKPIs>("/analytics/kpis"),
  getAnomalies: () => apiClient<AnomalyAlert[]>("/analytics/anomalies"),
  getChannels: () => apiClient<AnalyticsChannelState[]>("/analytics/channels"),
  getOverview: (brandId?: string, windowDays?: number) => {
    const params = new URLSearchParams();
    if (brandId) params.append("brand_id", brandId);
    if (windowDays) params.append("window_days", String(windowDays));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return apiClient<AnalyticsOverviewResponse>(`/analytics/overview${qs}`);
  },
};
