import { apiClient } from "../client";

export const mediaApi = {
  list: () => apiClient<any[]>("/media"),
  getPresigned: (filename: string = "asset.png") =>
    apiClient<any>(`/media/presigned?filename=${encodeURIComponent(filename)}`),
  uploadRecord: (data: any) =>
    apiClient<any>("/media/upload", { method: "POST", body: JSON.stringify(data) }),
};
