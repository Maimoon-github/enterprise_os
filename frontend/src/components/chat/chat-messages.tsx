"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useChatStore } from "@/stores/chat-store";
import { approvalsApi } from "@/lib/api/endpoints/approvals";
import { ResumeDialog } from "@/components/approvals/resume-dialog";

export function ChatMessages({
  onSelectSuggestion,
}: {
  onSelectSuggestion: (prompt: string) => void;
}) {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const activeRunId = useChatStore((s) => s.activeRunId);
  const activeNode = useChatStore((s) => s.activeNode);
  const activeApprovalId = useChatStore((s) => s.activeApprovalId);
  const activeApprovalPayload = useChatStore((s) => s.activeApprovalPayload);
  const setActiveApproval = useChatStore((s) => s.setActiveApproval);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [isApprovalAction, setIsApprovalAction] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent, isStreaming]);

  const handleApprove = () => {
    setIsApprovalAction(true);
    setDialogOpen(true);
  };

  const handleReject = () => {
    setIsApprovalAction(false);
    setDialogOpen(true);
  };

  const handleResumeSubmit = async (notes: string, approved: boolean) => {
    if (!activeApprovalId) return;
    try {
      await approvalsApi.resume(activeApprovalId, { approved, notes });
      setActiveApproval(null, null);
    } catch {}
  };

  const suggestions = [
    "Synthesize comprehensive Q4 multi-platform campaign blueprint for Apex Global",
    "Audit brand voice consistency across recent social posts using Tier 3 validator",
    "Run competitor reconnaissance on top 3 industry benchmarks",
    "Analyze cross-platform performance anomalies and recommend budget reallocations",
  ];

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-5 scrollbar-thin">
      {messages.length === 0 && !isStreaming ? (
        <div className="h-full flex flex-col items-center justify-center max-w-xl mx-auto text-center space-y-6 pt-12">
          <div className="h-12 w-12 rounded-2xl bg-glass-emerald border border-glass-specular flex items-center justify-center text-xl text-bloodstone-mint shadow-bloodstone-glow">
            ⌘
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-bold tracking-tight text-bloodstone-text">
              Agentic Orchestrator Control Plane
            </h2>
            <p className="text-xs text-bloodstone-text-muted leading-relaxed">
              Issue high-level natural language instructions to drive research, Brand RAG, creative synthesis,
              multi-platform publication fan-out, and anomaly evaluation with guaranteed human-in-the-loop oversight.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
            {suggestions.map((s, idx) => (
              <button
                key={idx}
                onClick={() => onSelectSuggestion(s)}
                className="p-3 glass-card text-xs text-bloodstone-text-muted hover:text-bloodstone-text hover:border-glass-specular transition duration-fast ease-out-expo flex items-center justify-between group"
              >
                <span className="line-clamp-2">{s}</span>
                <span className="text-bloodstone-mint opacity-0 group-hover:opacity-100 transition shrink-0 ml-2">
                  →
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          {messages.map((m) => {
            const isUser = m.role === "user";
            const runId = m.run_id;
            const meta = (m.metadata || {}) as Record<string, any>;

            return (
              <div
                key={m.id}
                className={`flex gap-3.5 ${isUser ? "justify-end" : "justify-start"}`}
              >
                {!isUser && (
                  <div className="h-7 w-7 rounded-lg bg-glass-emerald border border-glass-specular flex items-center justify-center font-bold text-xs text-bloodstone-mint shrink-0 mt-0.5 shadow-bloodstone-glow">
                    AG
                  </div>
                )}

                <div
                  className={`max-w-2xl rounded-2xl p-4 text-xs space-y-2.5 transition-all ${
                    isUser
                      ? "bg-glass-emerald/40 border border-glass-specular text-bloodstone-text ml-12"
                      : "glass-card text-bloodstone-text mr-12"
                  }`}
                >
                  <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>

                  {/* Attached Run & Subgraph Status Chips */}
                  {(runId || meta.thread_id) && (
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-glass-subtle/50 text-[11px]">
                      {runId && (
                        <Link
                          href={`/runs/${runId}`}
                          className="px-2 py-0.5 rounded bg-glass-base hover:bg-glass-elevated border border-glass-subtle text-bloodstone-mint hover:underline font-mono flex items-center gap-1"
                        >
                          <span>Run:</span>
                          <span>{String(runId).slice(0, 8)}...</span>
                          <span>↗</span>
                        </Link>
                      )}
                      {meta.status && (
                        <span className="px-2 py-0.5 rounded-full bg-glass-base border border-glass-subtle text-bloodstone-text-muted uppercase text-[10px] tracking-wider">
                          Status: {meta.status}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="h-7 w-7 rounded-lg bg-glass-base border border-glass-subtle flex items-center justify-center font-bold text-xs text-bloodstone-text shrink-0 mt-0.5">
                    U
                  </div>
                )}
              </div>
            );
          })}

          {/* Real-time Assistant Streaming Bubble */}
          {isStreaming && (
            <div className="flex gap-3.5 justify-start">
              <div className="h-7 w-7 rounded-lg bg-glass-emerald border border-glass-specular flex items-center justify-center font-bold text-xs text-bloodstone-mint shrink-0 mt-0.5 shadow-bloodstone-glow animate-pulse">
                AG
              </div>
              <div className="max-w-2xl rounded-2xl p-4 text-xs glass-card text-bloodstone-text space-y-2.5 mr-12">
                <div className="flex items-center gap-2 pb-1 border-b border-glass-subtle/60 text-[11px] text-bloodstone-text-muted">
                  <span className="h-2 w-2 rounded-full bg-bloodstone-mint animate-pulse"></span>
                  <span className="font-mono">
                    {activeNode ? `Executing: ${activeNode}` : "Orchestrating Workflow..."}
                  </span>
                  {activeRunId && (
                    <span className="font-mono text-bloodstone-text-dim">
                      ({String(activeRunId).slice(0, 8)})
                    </span>
                  )}
                </div>

                <div className="whitespace-pre-wrap leading-relaxed">
                  {streamingContent || "Initializing multi-agent pipeline..."}
                  <span className="inline-block animate-pulse text-bloodstone-mint ml-0.5">▋</span>
                </div>

                {/* Embedded Interactive Approval Card if graph interrupted */}
                {activeApprovalId && (
                  <div className="mt-3 p-3.5 glass-crimson rounded-xl space-y-2.5 border border-bloodstone-crimson/80">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-bloodstone-text uppercase tracking-wider flex items-center gap-1.5">
                        <span>⚠️</span>
                        <span>Human Approval Required</span>
                      </span>
                      <span className="text-[10px] font-mono text-bloodstone-text/70">
                        Approval {activeApprovalId.slice(0, 8)}
                      </span>
                    </div>

                    <p className="text-xs text-bloodstone-text/90 leading-normal">
                      Campaign blueprint synthesized. Multi-platform publish fanout halted pending human sign-off.
                    </p>

                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        onClick={handleReject}
                        className="px-3 py-1.5 bg-black/40 hover:bg-black/60 border border-white/20 text-xs rounded-lg font-medium text-bloodstone-text transition"
                      >
                        Request Revision
                      </button>
                      <button
                        onClick={handleApprove}
                        className="px-3 py-1.5 glass-emerald text-xs rounded-lg font-medium text-bloodstone-text transition"
                      >
                        Approve & Publish
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Resume / Revision Modal */}
      <ResumeDialog
        isOpen={dialogOpen}
        approvalId={activeApprovalId || undefined}
        isApprovalAction={isApprovalAction}
        onClose={() => setDialogOpen(false)}
        onResume={handleResumeSubmit}
      />
    </div>
  );
}
