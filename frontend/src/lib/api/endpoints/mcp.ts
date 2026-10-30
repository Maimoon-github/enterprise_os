import { apiClient } from "../client";

export const mcpApi = {
  list: () => apiClient<any[]>("/mcp-servers"),
  sync: (serverId: string) => apiClient<any>(`/mcp-servers/${serverId}/sync`, { method: "POST" }),
};
