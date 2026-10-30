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
                  ? "bg-rose-500"
                  : isInterrupted
                  ? "bg-amber-400"
                  : isCompleted
                  ? "bg-emerald-400"
                  : "bg-indigo-400 animate-pulse"
              }`}
            />
            <span
              className={`text-xs font-semibold uppercase tracking-wider font-mono ${
                isFailed
                  ? "text-rose-400"
                  : isInterrupted
                  ? "text-amber-400"
                  : isCompleted
                  ? "text-emerald-400"
                  : "text-indigo-400"
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
          <h1 className="text-2xl font-bold tracking-tight text-white mt-1">
            Run {runId.slice(0, 18)}
          </h1>
          {runDetails?.thread_id && (
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Thread: {runDetails.thread_id} • Campaign: {String(runDetails.campaign_id).slice(0, 12)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/campaigns"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 rounded-lg transition"
          >
            ← Campaigns
          </Link>
          {isInterrupted && (
            <Link
              href="/approvals"
              className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-500 text-xs font-semibold text-white rounded-lg transition"
            >
              Open Approvals Queue →
            </Link>
          )}
        </div>
      </div>

      {isInterrupted && (
        <div className="p-4 bg-amber-950/30 border border-amber-800 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-300 uppercase tracking-wider">
              Human-in-the-Loop Interrupt Active
            </span>
            <Link
              href="/approvals"
              className="text-xs px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded font-medium transition"
            >
              Review in Approvals Queue →
            </Link>
          </div>
          <p className="text-xs text-amber-200/90 leading-relaxed">
            Execution suspended at super-step boundary <code className="bg-amber-900/50 px-1 py-0.5 rounded font-mono">human_approval_gate_node</code>. Checkpoint snapshot safely persisted to PostgresSaver checkpointer.
          </p>
          {interruptedPayload && (
            <pre className="mt-2 p-3 bg-amber-950/60 border border-amber-900/50 rounded-lg text-[11px] font-mono text-amber-200 overflow-x-auto">
              {JSON.stringify(interruptedPayload, null, 2)}
            </pre>
          )}
        </div>
      )}

      {isFailed && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-xs space-y-1">
          <span className="font-semibold uppercase tracking-wider">Execution Error</span>
          <p className="font-mono">{errorMessage || runDetails?.error_message || "Graph execution encountered an unhandled exception."}</p>
        </div>
      )}

      {isCompleted && (
        <div className="p-4 bg-emerald-950/30 border border-emerald-800 rounded-xl text-emerald-300 text-xs flex items-center justify-between">
          <div>
            <span className="font-semibold uppercase tracking-wider">All Super-Steps Completed</span>
            <p className="text-emerald-200/80 mt-0.5">Campaign blueprint generated, approved, and dispatched across platforms.</p>
          </div>
          {runDetails?.token_usage && (
            <div className="text-right font-mono text-[11px] text-emerald-400">
              Total Tokens: {Number(runDetails.token_usage.total_tokens || 0).toLocaleString()}
            </div>
          )}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
          LangGraph Execution DAG
        </h2>
        <GraphVisualizer currentNode={currentNode} nodeStates={nodeStates} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
              Execution Event Stream
            </h2>
            <span className="text-xs text-slate-500 font-mono">{events.length} event(s)</span>
          </div>
          <NodeTimeline events={events} />
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
            Active Tool Call Inspector
          </h2>
          <ToolCallInspector toolCall={activeToolCall} />
        </div>
      </div>
    </div>
  );
}
