"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useChatStore } from "@/stores/chat-store";
import { chatApi } from "@/lib/api/endpoints/chat";
import { ChatSessionResponse } from "@marketing-os/contracts";

export function ChatSidebar({
  onSelectSession,
  onCreateNewSession,
}: {
  onSelectSession: (id: string) => void;
  onCreateNewSession: () => void;
}) {
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const setSessions = useChatStore((s) => s.setSessions);
  const updateSessionInList = useChatStore((s) => s.updateSessionInList);
  const removeSessionFromList = useChatStore((s) => s.removeSessionFromList);
  const searchQuery = useChatStore((s) => s.searchQuery);
  const setSearchQuery = useChatStore((s) => s.setSearchQuery);

  const [isEditingId, setIsEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  useEffect(() => {
    chatApi
      .listSessions({ is_archived: false })
      .then((data) => setSessions(data))
      .catch(() => {});
  }, [setSessions]);

  const handleTogglePin = async (e: React.MouseEvent, session: ChatSessionResponse) => {
    e.stopPropagation();
    try {
      const updated = await chatApi.updateSession(session.id, {
        is_pinned: !session.is_pinned,
      });
      updateSessionInList(updated);
    } catch {}
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Delete this chat session?")) return;
    try {
      await chatApi.deleteSession(id);
      removeSessionFromList(id);
    } catch {}
  };

  const handleRenameSubmit = async (e: React.FormEvent, id: string) => {
    e.preventDefault();
    if (!editingTitle.trim()) return;
    try {
      const updated = await chatApi.updateSession(id, { title: editingTitle.trim() });
      updateSessionInList(updated);
      setIsEditingId(null);
    } catch {}
  };

  const filtered = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const pinned = filtered.filter((s) => s.is_pinned);
  const recent = filtered.filter((s) => !s.is_pinned);

  return (
    <div className="w-72 glass-panel border-r border-glass-subtle flex flex-col justify-between shrink-0 h-[calc(100vh-4rem)]">
      <div className="p-4 space-y-3 flex-1 overflow-y-auto scrollbar-thin">
        {/* Top Header & New Chat Button */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-bloodstone-text-muted uppercase tracking-wider">
            Conversations
          </span>
          <button
            onClick={onCreateNewSession}
            title="Start New Orchestrator Chat (Ctrl+K)"
            className="px-2.5 py-1 text-xs glass-emerald rounded-lg text-bloodstone-text font-medium flex items-center gap-1.5 active:scale-[0.98] transition"
          >
            <span>+</span>
            <span>New Chat</span>
          </button>
        </div>

        {/* Search */}
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full glass-input px-3 py-1.5 text-xs text-bloodstone-text placeholder:text-bloodstone-text-dim"
          />
        </div>

        {/* Pinned Chats */}
        {pinned.length > 0 && (
          <div className="space-y-1 pt-2">
            <div className="text-[10px] uppercase font-bold text-bloodstone-mint tracking-wider px-2">
              📌 Pinned ({pinned.length})
            </div>
            {pinned.map((s) => (
              <div
                key={s.id}
                onClick={() => onSelectSession(s.id)}
                className={`group px-2.5 py-2 rounded-lg text-xs cursor-pointer flex items-center justify-between transition-all duration-fast ${
                  activeSessionId === s.id
                    ? "bg-glass-emerald border border-glass-specular text-bloodstone-mint shadow-bloodstone-glow"
                    : "text-bloodstone-text-muted hover:bg-glass-base hover:text-bloodstone-text"
                }`}
              >
                <div className="truncate flex-1 pr-2">
                  <span className="truncate block font-medium">{s.title}</span>
                  <span className="text-[10px] text-bloodstone-text-dim">
                    {s.messages_count} msgs
                  </span>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                  <button
                    onClick={(e) => handleTogglePin(e, s)}
                    title="Unpin"
                    className="p-1 text-bloodstone-mint hover:bg-black/30 rounded"
                  >
                    📌
                  </button>
                  <button
                    onClick={(e) => handleDelete(e, s.id)}
                    title="Delete"
                    className="p-1 text-rose-400 hover:bg-black/30 rounded"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Recent Chats */}
        <div className="space-y-1 pt-2">
          <div className="text-[10px] uppercase font-bold text-bloodstone-text-dim tracking-wider px-2">
            Recent Chats ({recent.length})
          </div>
          {recent.length === 0 ? (
            <div className="p-4 text-center text-xs text-bloodstone-text-dim">
              No conversations found.
            </div>
          ) : (
            recent.map((s) => {
              const isActive = activeSessionId === s.id;
              return (
                <div
                  key={s.id}
                  onClick={() => onSelectSession(s.id)}
                  className={`group px-2.5 py-2 rounded-lg text-xs cursor-pointer flex items-center justify-between transition-all duration-fast ${
                    isActive
                      ? "bg-glass-emerald border border-glass-specular text-bloodstone-mint shadow-bloodstone-glow"
                      : "text-bloodstone-text-muted hover:bg-glass-base hover:text-bloodstone-text"
                  }`}
                >
                  {isEditingId === s.id ? (
                    <form
                      onSubmit={(e) => handleRenameSubmit(e, s.id)}
                      className="flex-1 flex gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        className="w-full bg-black/60 border border-bloodstone-mint rounded px-1.5 py-0.5 text-xs text-bloodstone-text"
                        autoFocus
                        onBlur={() => setIsEditingId(null)}
                      />
                    </form>
                  ) : (
                    <div className="truncate flex-1 pr-2">
                      <span className="truncate block font-medium">{s.title}</span>
                      <span className="text-[10px] text-bloodstone-text-dim">
                        {s.messages_count} msgs
                      </span>
                    </div>
                  )}

                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsEditingId(s.id);
                        setEditingTitle(s.title);
                      }}
                      title="Rename"
                      className="p-1 text-bloodstone-text-muted hover:text-bloodstone-mint hover:bg-black/30 rounded"
                    >
                      ✎
                    </button>
                    <button
                      onClick={(e) => handleTogglePin(e, s)}
                      title="Pin chat"
                      className="p-1 text-bloodstone-text-muted hover:text-bloodstone-mint hover:bg-black/30 rounded"
                    >
                      📍
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, s.id)}
                      title="Delete chat"
                      className="p-1 text-rose-400 hover:bg-black/30 rounded"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Bottom Footer: Platform Settings shortcut */}
      <div className="p-3 border-t border-glass-dark bg-glass-base/50 flex items-center justify-between text-xs">
        <Link
          href="/settings"
          className="text-bloodstone-text-muted hover:text-bloodstone-mint flex items-center gap-1.5 transition"
        >
          <span>⚙️</span>
          <span>Platform Settings</span>
        </Link>
        <span className="text-[10px] text-bloodstone-text-dim font-mono">Control Plane v1.0</span>
      </div>
    </div>
  );
}
