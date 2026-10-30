import { apiClient } from "../client";
import { BeatScheduleModel, ScheduleModel } from "@/types/models";

export const schedulesApi = {
  list: () => apiClient<ScheduleModel[]>("/schedules"),
  listBeat: () => apiClient<BeatScheduleModel[]>("/schedules/beat"),
  triggerBeat: (scheduleName: string) =>
    apiClient<{ status: string; schedule_name: string; task_id?: string }>(
      `/schedules/beat/${encodeURIComponent(scheduleName)}/trigger`,
      { method: "POST" }
    ),
  delete: (id: string) =>
    apiClient<void>(`/schedules/${id}`, {
      method: "DELETE",
    }),
};
