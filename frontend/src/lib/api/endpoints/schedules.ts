import { apiClient } from "../client";

export const schedulesApi = {
  list: () => apiClient<any[]>("/schedules"),
};
