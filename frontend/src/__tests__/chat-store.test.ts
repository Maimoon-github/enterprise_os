import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";

describe("ChatStore", () => {
  beforeEach(() => {
    useChatStore.setState({
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
    });
  });

  it("should initialize with default empty state", () => {
    const state = useChatStore.getState();
    expect(state.sessions).toEqual([]);
    expect(state.activeSessionId).toBeNull();
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
  });

  it("should manage chat sessions correctly", () => {
    const mockSession = {
      id: "sess-1",
      user_id: "user-1",
      title: "Test Campaign Session",
      is_pinned: false,
      is_archived: false,
      messages_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    useChatStore.getState().addSession(mockSession);
    expect(useChatStore.getState().sessions).toHaveLength(1);
    expect(useChatStore.getState().sessions[0].id).toBe("sess-1");

    useChatStore.getState().setActiveSessionId("sess-1");
    expect(useChatStore.getState().activeSessionId).toBe("sess-1");

    useChatStore.getState().removeSessionFromList("sess-1");
    expect(useChatStore.getState().sessions).toHaveLength(0);
  });

  it("should handle streaming deltas and active approval interrupts", () => {
    useChatStore.getState().setIsStreaming(true);
    expect(useChatStore.getState().isStreaming).toBe(true);

    useChatStore.getState().appendStreamingDelta("Drafting campaign ");
    useChatStore.getState().appendStreamingDelta("blueprint...");
    expect(useChatStore.getState().streamingContent).toBe("Drafting campaign blueprint...");

    useChatStore.getState().setActiveApproval("appr-123", { gate: "pre_publish", run_id: "run-456" });
    expect(useChatStore.getState().activeApprovalId).toBe("appr-123");
    expect(useChatStore.getState().activeApprovalPayload?.gate).toBe("pre_publish");

    useChatStore.getState().resetStream();
    expect(useChatStore.getState().isStreaming).toBe(false);
    expect(useChatStore.getState().streamingContent).toBe("");
  });
});
