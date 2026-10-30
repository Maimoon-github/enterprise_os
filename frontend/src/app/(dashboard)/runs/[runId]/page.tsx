"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { GraphVisualizer } from "@/components/runs/graph-visualizer";
import { NodeTimeline } from "@/components/runs/node-timeline";
import { ToolCallInspector } from "@/components/runs/tool-call-inspector";
import { useRunStream } from "@/hooks/use-run-stream";
import { useRunStore } from "@/stores/run-store";
import { runsApi } from "@/lib/api/endpoints/runs";
import { RunResponse } from "@marketing-os/contracts";

export default function RunExecutionPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = use(params);
  const { events } = useRunStream(runId);
  const nodeStates = useRunStore((s) => s.nodeStates);
  const activeToolCall = useRunStore((s) => s.activeToolCall);
  const interruptedPayload = useRunStore((s) => s.interruptedPayload);
  const runStatus = useRunStore((s) => s.runStatus);
  const errorMessage = useRunStore((s) => s.errorMessage);

  const [currentNode, setCurrentNode] = useState<string>("supervisor_router");
  const [runDetails, setRunDetails] = useState<RunResponse | null>(null);

  useEffect(() => {
    runsApi
      .get(runId)
      .then((data) => {
        if (data) {
          setRunDetails(data);
          if (data.current_node) {
            setCurrentNode(data.current_node);
          }
        }
      })
      .catch(() => {});
  }, [runId]);

  useEffect(() => {
    if (events.length > 0) {
      const latest = events[events.length - 1];
      if (latest.data?.node) {
        setCurrentNode(latest.data.node);
      }
    }
  }, [events]);

  const isInterrupted =
    runStatus === "interrupted" ||
    runDetails?.status === "interrupted" ||
    Object.values(nodeStates).some((n) => n.status === "interrupted");

  const isCompleted =
    runStatus === "completed" || runDetails?.status === "completed";

  const isFailed =
    runStatus === "failed" || runDetails?.status === "failed" || !!errorMessage;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isFailed
                  ? "bg-bloodstone-crimson"
                  : isInterrupted
                  ? "bg-bloodstone-crimson shadow-crimson-glow"
                  : isCompleted
                  ? "bg-bloodstone-mint shadow-[0_0_8px_#7bf0a7]"
                  : "bg-bloodstone-mint animate-pulse"
              }`}
            />
            <span
              className={`text-xs font-semibold uppercase tracking-wider font-mono ${
                isFailed
                  ? "text-rose-400"
                  : isInterrupted
                  ? "text-rose-300"
                  : isCompleted
                  ? "text-bloodstone-mint"
                  : "text-bloodstone-mint"
              }`}
            >
              {isFailed
                ? "Execution Failed"
                : isInterrupted
                ? "Halted at Interrupt Boundary (HITL Gate)"
                : isCompleted
                ? "Graph Execution Finalized"
                : "Live LangGraph Execution Active"}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-bloodstone-text mt-1">
            Run {runId.slice(0, 18)}
          </h1>
          {runDetails?.thread_id && (
            <p className="text-xs text-bloodstone-text-muted font-mono mt-0.5">
              Thread: {runDetails.thread_id} • Campaign: {String(runDetails.campaign_id).slice(0, 12)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/campaigns"
            className="px-3 py-1.5 bg-glass-base hover:bg-glass-elevated border border-glass-subtle text-xs font-medium text-bloodstone-text rounded-lg transition duration-fast ease-out-expo"
          >
            ← Campaigns
          </Link>
          {isInterrupted && (
            <Link
              href="/approvals"
              className="px-3.5 py-1.5 glass-crimson text-xs font-semibold rounded-lg transition duration-fast ease-out-expo"
            >
              Open Approvals Queue →
            </Link>
          )}
        </div>
      </div>

      {isInterrupted && (
        <div className="p-4 glass-crimson rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-bloodstone-text uppercase tracking-wider">
              Human-in-the-Loop Interrupt Active
            </span>
            <Link
              href="/approvals"
              className="text-xs px-3 py-1 bg-bloodstone-crimson hover:bg-red-700 text-bloodstone-text rounded-lg font-medium transition duration-fast ease-out-expo"
            >
              Review in Approvals Queue →
            </Link>
          </div>
          <p className="text-xs text-bloodstone-text/90 leading-relaxed">
            Execution suspended at super-step boundary <code className="bg-black/30 px-1 py-0.5 rounded font-mono">human_approval_gate_node</code>. Checkpoint snapshot safely persisted to PostgresSaver checkpointer.
          </p>
          {interruptedPayload && (
            <pre className="mt-2 p-3 bg-black/40 border border-red-500/30 rounded-lg text-[11px] font-mono text-bloodstone-text overflow-x-auto scrollbar-thin">
              {JSON.stringify(interruptedPayload, null, 2)}
            </pre>
          )}
        </div>
      )}

      {isFailed && (
        <div className="p-4 glass-crimson rounded-xl text-rose-200 text-xs space-y-1">
          <span className="font-semibold uppercase tracking-wider">Execution Error</span>
          <p className="font-mono">{errorMessage || runDetails?.error_message || "Graph execution encountered an unhandled exception."}</p>
        </div>
      )}

      {isCompleted && (
        <div className="p-4 glass-emerald rounded-xl text-bloodstone-mint text-xs flex items-center justify-between">
          <div>
            <span className="font-semibold uppercase tracking-wider text-bloodstone-text">All Super-Steps Completed</span>
            <p className="text-bloodstone-text-muted mt-0.5">Campaign blueprint generated, approved, and dispatched across platforms.</p>
          </div>
          {runDetails?.token_usage && (
            <div className="text-right font-mono text-[11px] text-bloodstone-mint">
              Total Tokens: {Number(runDetails.token_usage.total_tokens || 0).toLocaleString()}
            </div>
          )}
        </div>
      )}

      <div className="glass-card p-6 space-y-4">
        <h2 className="text-sm font-semibold uppercase text-bloodstone-text-muted tracking-wider">
          LangGraph Execution DAG
        </h2>
        <GraphVisualizer currentNode={currentNode} nodeStates={nodeStates} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase text-bloodstone-text-muted tracking-wider">
              Execution Event Stream
            </h2>
            <span className="text-xs text-bloodstone-text-dim font-mono">{events.length} event(s)</span>
          </div>
          <NodeTimeline events={events} />
        </div>

        <div className="glass-card p-6 space-y-4">
          <h2 className="text-sm font-semibold uppercase text-bloodstone-text-muted tracking-wider">
            Active Tool Call Inspector
          </h2>
          <ToolCallInspector toolCall={activeToolCall} />
        </div>
      </div>
    </div>
  );
}
