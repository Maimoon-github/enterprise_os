import { create } from "zustand";
import {
  ChatSessionResponse,
  ChatSessionDetailResponse,
  ChatMessageResponse,
} from "@marketing-os/contracts";

interface ChatStore {
  sessions: ChatSessionResponse[];
  activeSessionId: string | null;
  activeSession: ChatSessionDetailResponse | null;
  messages: ChatMessageResponse[];
  isStreaming: boolean;
  streamingContent: string;
  activeRunId: string | null;
  activeApprovalId: string | null;
  activeApprovalPayload: Record<string, any> | null;
  activeNode: string | null;
  sidebarOpen: boolean;
  searchQuery: string;

  setSessions: (sessions: ChatSessionResponse[]) => void;
  addSession: (session: ChatSessionResponse) => void;
  updateSessionInList: (session: ChatSessionResponse) => void;
  removeSessionFromList: (sessionId: string) => void;
  setActiveSessionId: (id: string | null) => void;
  setActiveSession: (session: ChatSessionDetailResponse | null) => void;
  setMessages: (messages: ChatMessageResponse[]) => void;
  addMessage: (message: ChatMessageResponse) => void;
  appendStreamingDelta: (delta: string) => void;
  setIsStreaming: (val: boolean) => void;
  setActiveRunId: (id: string | null) => void;
  setActiveApproval: (id: string | null, payload: Record<string, any> | null) => void;
  setActiveNode: (node: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setSearchQuery: (query: string) => void;
  resetStream: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  sessions: [],
  activeSessionId: null,
  activeSession: null,
  messages: [],
  isStreaming: false,
  streamingContent: "",
  activeRunId: null,
  activeApprovalId: null,
  activeApprovalPayload: null,
  activeNode: null,
  sidebarOpen: true,
  searchQuery: "",

  setSessions: (sessions) => set({ sessions }),
  addSession: (session) => set((prev) => ({ sessions: [session, ...prev.sessions] })),
  updateSessionInList: (session) =>
    set((prev) => ({
      sessions: prev.sessions.map((s) => (s.id === session.id ? session : s)),
    })),
  removeSessionFromList: (sessionId) =>
    set((prev) => ({
      sessions: prev.sessions.filter((s) => s.id !== sessionId),
      activeSessionId: prev.activeSessionId === sessionId ? null : prev.activeSessionId,
      activeSession: prev.activeSession?.id === sessionId ? null : prev.activeSession,
    })),
  setActiveSessionId: (id) => set({ activeSessionId: id }),
  setActiveSession: (session) =>
    set({
      activeSession: session,
      activeSessionId: session ? session.id : null,
      messages: session ? (session.messages || []) : [],
    }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((prev) => ({ messages: [...prev.messages, message] })),
  appendStreamingDelta: (delta) =>
    set((prev) => ({ streamingContent: prev.streamingContent + delta })),
  setIsStreaming: (val) => set({ isStreaming: val }),
  setActiveRunId: (id) => set({ activeRunId: id }),
  setActiveApproval: (id, payload) => set({ activeApprovalId: id, activeApprovalPayload: payload }),
  setActiveNode: (node) => set({ activeNode: node }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((prev) => ({ sidebarOpen: !prev.sidebarOpen })),
  setSearchQuery: (query) => set({ searchQuery: query }),
  resetStream: () =>
    set({
      isStreaming: false,
      streamingContent: "",
      activeRunId: null,
      activeApprovalId: null,
      activeApprovalPayload: null,
      activeNode: null,
    }),
}));
