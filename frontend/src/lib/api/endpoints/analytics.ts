import { apiClient } from "../client";

export const analyticsApi = {
  getKPIs: () => apiClient<any>("/analytics/kpis"),
  getAnomalies: () => apiClient<any[]>("/analytics/anomalies"),
};
