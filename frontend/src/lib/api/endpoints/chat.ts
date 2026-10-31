import { apiClient } from "../client";
import {
  ChatSessionCreate,
  ChatSessionResponse,
  ChatSessionDetailResponse,
  ChatSessionUpdate,
  ChatMessageCreate,
  ChatMessageResponse,
} from "@marketing-os/contracts";

export const chatApi = {
  listSessions: (params?: {
    is_pinned?: boolean;
    is_archived?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.is_pinned !== undefined) q.append("is_pinned", String(params.is_pinned));
    if (params?.is_archived !== undefined) q.append("is_archived", String(params.is_archived));
    if (params?.search) q.append("search", params.search);
    if (params?.limit !== undefined) q.append("limit", String(params.limit));
    if (params?.offset !== undefined) q.append("offset", String(params.offset));
    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return apiClient<ChatSessionResponse[]>(`/chat/sessions${queryStr}`);
  },

  getSession: (sessionId: string) =>
    apiClient<ChatSessionDetailResponse>(`/chat/sessions/${sessionId}`),

  createSession: (data: ChatSessionCreate = {}) =>
    apiClient<ChatSessionResponse>("/chat/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateSession: (sessionId: string, data: ChatSessionUpdate) =>
    apiClient<ChatSessionResponse>(`/chat/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteSession: (sessionId: string) =>
    apiClient<void>(`/chat/sessions/${sessionId}`, {
      method: "DELETE",
    }),

  sendMessage: (sessionId: string, data: ChatMessageCreate) =>
    apiClient<ChatMessageResponse>(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
