"use client";

import { useCallback } from "react";
import { useChatStore } from "@/stores/chat-store";
import { chatApi } from "@/lib/api/endpoints/chat";
import { ensureAuthToken } from "@/lib/api/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function useChatStream() {
  const isStreaming = useChatStore((s) => s.isStreaming);
  const setIsStreaming = useChatStore((s) => s.setIsStreaming);
  const appendStreamingDelta = useChatStore((s) => s.appendStreamingDelta);
  const setActiveRunId = useChatStore((s) => s.setActiveRunId);
  const setActiveApproval = useChatStore((s) => s.setActiveApproval);
  const setActiveNode = useChatStore((s) => s.setActiveNode);
  const resetStream = useChatStore((s) => s.resetStream);
  const addMessage = useChatStore((s) => s.addMessage);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  const sendMessageStream = useCallback(
    async (sessionId: string, content: string) => {
      if (!content.trim() || isStreaming) return;

      let token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      if (!token) {
        token = await ensureAuthToken();
      }

      // Optimistically append user message to local state
      const tempUserMsg = {
        id: "temp-" + Date.now(),
        session_id: sessionId,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      addMessage(tempUserMsg);

      setIsStreaming(true);
      resetStream();
      setIsStreaming(true);

      try {
        const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ content, stream: true }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server error ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) {
          throw new Error("No response stream body available");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const block of lines) {
            const rawLines = block.split("\n");
            let eventType = "message";
            let dataStr = "";

            for (const line of rawLines) {
              if (line.startsWith("event: ")) {
                eventType = line.replace("event: ", "").trim();
              } else if (line.startsWith("data: ")) {
                dataStr = line.replace("data: ", "").trim();
              }
            }

            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);

              if (eventType === "run_start") {
                if (data.run_id) setActiveRunId(data.run_id);
              } else if (eventType === "delta") {
                if (data.text) appendStreamingDelta(data.text);
              } else if (eventType === "node_start" || eventType === "node_transition") {
                if (data.node) setActiveNode(data.node);
              } else if (eventType === "interrupt") {
                if (data.approval_id) {
                  setActiveApproval(data.approval_id, data.payload || null);
                }
                if (data.node) setActiveNode(data.node);
              } else if (eventType === "complete") {
                setActiveNode(null);
                // Synchronize full session messages from DB
                const freshSession = await chatApi.getSession(sessionId);
                setActiveSession(freshSession);
              } else if (eventType === "error") {
                appendStreamingDelta(`\n\n❌ Error: ${data.error || "Unknown error"}`);
              }
            } catch {
              // Ignore partial JSON parse errors
            }
          }
        }
      } catch (err: any) {
        appendStreamingDelta(`\n\n❌ Request failed: ${err.message || String(err)}`);
      } finally {
        setIsStreaming(false);
      }
    },
    [
      isStreaming,
      addMessage,
      setIsStreaming,
      resetStream,
      setActiveRunId,
      appendStreamingDelta,
      setActiveNode,
      setActiveApproval,
      setActiveSession,
    ]
  );

  return {
    sendMessageStream,
    isStreaming,
  };
}
