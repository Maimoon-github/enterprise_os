"use client";

import { useEffect, useCallback } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useChatStream } from "@/hooks/use-chat-stream";
import { chatApi } from "@/lib/api/endpoints/chat";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { ChatMessages } from "@/components/chat/chat-messages";
import { ChatComposer } from "@/components/chat/chat-composer";

export default function OrchestratorChatPage() {
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const activeSession = useChatStore((s) => s.activeSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const addSession = useChatStore((s) => s.addSession);
  const sidebarOpen = useChatStore((s) => s.sidebarOpen);
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const { sendMessageStream } = useChatStream();

  const handleSelectSession = useCallback(
    async (id: string) => {
      try {
        const fullSession = await chatApi.getSession(id);
        setActiveSession(fullSession);
      } catch {}
    },
    [setActiveSession]
  );

  const handleCreateNewSession = useCallback(async () => {
    try {
      const created = await chatApi.createSession({ title: "New Orchestrator Chat" });
      addSession(created);
      const full = await chatApi.getSession(created.id);
      setActiveSession(full);
    } catch {}
  }, [addSession, setActiveSession]);

  useEffect(() => {
    // Initial session loading
    chatApi
      .listSessions({ limit: 1 })
      .then((sessions) => {
        if (sessions.length > 0) {
          handleSelectSession(sessions[0].id);
        } else {
          handleCreateNewSession();
        }
      })
      .catch(() => {});
  }, [handleSelectSession, handleCreateNewSession]);

  // Global hotkey Ctrl+K / Cmd+K to start new chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        handleCreateNewSession();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleCreateNewSession]);

  const handleSendMessage = async (content: string) => {
    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      const newSession = await chatApi.createSession({ title: "New Orchestrator Chat" });
      addSession(newSession);
      targetSessionId = newSession.id;
      const full = await chatApi.getSession(newSession.id);
      setActiveSession(full);
    }
    await sendMessageStream(targetSessionId, content);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] -m-8 overflow-hidden">
      {/* Collapsible Sidebar */}
      {sidebarOpen && (
        <ChatSidebar
          onSelectSession={handleSelectSession}
          onCreateNewSession={handleCreateNewSession}
        />
      )}

      {/* Main Chat Workstation */}
      <div className="flex-1 flex flex-col min-w-0 bg-transparent relative">
        {/* Chat Control Plane Header */}
        <div className="h-14 border-b border-glass-subtle bg-glass-base/40 px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={toggleSidebar}
              title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              className="p-1.5 glass-card rounded-lg text-xs text-bloodstone-text-muted hover:text-bloodstone-text transition"
            >
              {sidebarOpen ? "◀" : "▶"}
            </button>
            <div>
              <div className="text-sm font-semibold text-bloodstone-text flex items-center gap-2">
                <span>{activeSession?.title || "Orchestrator Workspace"}</span>
                {activeSession?.is_pinned && <span title="Pinned">📌</span>}
              </div>
              <div className="text-[10px] text-bloodstone-text-dim font-mono">
                Session: {activeSessionId ? activeSessionId.slice(0, 18) : "None"} • 8 MCP Proxies Connected
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCreateNewSession}
              className="px-3 py-1.5 text-xs glass-card hover:border-glass-specular text-bloodstone-text rounded-lg font-medium transition flex items-center gap-1.5"
            >
              <span>+ New Chat</span>
              <kbd className="hidden sm:inline text-[9px] bg-black/40 px-1 py-0.5 rounded text-bloodstone-text-dim">
                ⌘K
              </kbd>
            </button>
          </div>
        </div>

        {/* Message Thread */}
        <ChatMessages onSelectSuggestion={handleSendMessage} />

        {/* Composer */}
        <ChatComposer onSendMessage={handleSendMessage} />
      </div>
    </div>
  );
}
