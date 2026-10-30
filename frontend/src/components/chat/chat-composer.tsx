"use client";

import { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chat-store";

export function ChatComposer({
  onSendMessage,
}: {
  onSendMessage: (content: string) => void;
}) {
  const [content, setContent] = useState("");
  const isStreaming = useChatStore((s) => s.isStreaming);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!content.trim() || isStreaming) return;
    onSendMessage(content.trim());
    setContent("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [content]);

  return (
    <div className="p-4 border-t border-glass-subtle bg-glass-base/30 space-y-2.5">
      <div className="relative flex items-end gap-2 glass-panel rounded-2xl p-2 border border-glass-subtle focus-within:border-bloodstone-mint transition duration-fast">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Issue high-level instruction to orchestrator (e.g. 'Synthesize Q4 LinkedIn campaign', 'Audit brand tone')... [Enter to send]"
          rows={1}
          disabled={isStreaming}
          className="w-full bg-transparent px-3 py-2 text-xs text-bloodstone-text placeholder:text-bloodstone-text-dim focus:outline-none resize-none max-h-44 scrollbar-thin"
        />

        <button
          onClick={handleSend}
          disabled={!content.trim() || isStreaming}
          className="px-4 py-2 rounded-xl glass-emerald text-xs font-semibold text-bloodstone-text disabled:opacity-40 disabled:pointer-events-none transition duration-fast ease-out-expo flex items-center gap-1.5 shrink-0"
        >
          {isStreaming ? (
            <>
              <span className="h-2 w-2 rounded-full bg-bloodstone-mint animate-pulse"></span>
              <span>Running...</span>
            </>
          ) : (
            <>
              <span>Execute</span>
              <span>↵</span>
            </>
          )}
        </button>
      </div>

      <div className="flex items-center justify-between text-[11px] text-bloodstone-text-dim px-2">
        <div className="flex items-center gap-2">
          <span>🛡️ Sandboxed</span>
          <span>•</span>
          <span>OpenInference Traced</span>
          <span>•</span>
          <span>HITL Approval Gated</span>
        </div>
        <div>
          <span>Shift+Enter for newline</span>
        </div>
      </div>
    </div>
  );
}
