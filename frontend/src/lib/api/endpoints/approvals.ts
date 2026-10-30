import { apiClient } from "../client";
import { ApprovalResponse, ApprovalResumeRequest } from "@marketing-os/contracts";

export const approvalsApi = {
  list: () => apiClient<ApprovalResponse[]>("/approvals"),
  resume: (id: string, data: ApprovalResumeRequest) =>
    apiClient<{ status: string }>(`/approvals/${id}/resume`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
