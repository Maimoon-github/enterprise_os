import { apiClient } from "../client";

export const skillsApi = {
  list: () => apiClient<any[]>("/skills"),
};
