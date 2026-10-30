import { apiClient } from "../client";

export const mcpApi = {
  list: () => apiClient<any[]>("/mcp-servers"),
};
