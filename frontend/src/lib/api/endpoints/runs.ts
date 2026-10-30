import { apiClient } from "../client";
import { RunResponse, RunCreate } from "@marketing-os/contracts";

export const runsApi = {
  dispatch: (data: RunCreate) =>
    apiClient<RunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
