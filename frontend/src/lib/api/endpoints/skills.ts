import { apiClient } from "../client";

export const skillsApi = {
  list: () => apiClient<any[]>("/skills"),
  get: (name: string) => apiClient<any>(`/skills/${name}`),
  validate: (payload: { name: string; content: string }) =>
    apiClient<any>("/skills/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
