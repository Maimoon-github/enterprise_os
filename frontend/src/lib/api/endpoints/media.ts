import { apiClient } from "../client";

export const mediaApi = {
  list: () => apiClient<any[]>("/media"),
};
