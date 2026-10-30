"use client";

import { use, useEffect, useState } from "react";
import { GraphVisualizer } from "@/components/runs/graph-visualizer";
import { NodeTimeline } from "@/components/runs/node-timeline";
import { ToolCallInspector } from "@/components/runs/tool-call-inspector";
import { useRunStream } from "@/hooks/use-run-stream";
import { useRunStore } from "@/stores/run-store";

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

  const [currentNode, setCurrentNode] = useState<string>("supervisor_router");

  useEffect(() => {
    if (events.length > 0) {
      const latest = events[events.length - 1];
      if (latest.data?.node) {
        setCurrentNode(latest.data.node);
      }
    }
  }, [events]);

  const isInterrupted = Object.values(nodeStates).some((n) => n.status === "interrupted");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isInterrupted ? "bg-amber-400" : "bg-emerald-500 animate-pulse"
              }`}
            />
            <span
              className={`text-xs font-semibold uppercase tracking-wider ${
                isInterrupted ? "text-amber-400" : "text-emerald-400"
              }`}
            >
              {isInterrupted ? "Halted at Interrupt Boundary" : "Live LangGraph Execution"}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white mt-1">Run {runId}</h1>
        </div>
      </div>

      {interruptedPayload && (
        <div className="p-4 bg-amber-950/30 border border-amber-800 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-300 uppercase tracking-wider">
              Human-in-the-Loop Interrupt Active
            </span>
            <a
              href="/approvals"
              className="text-xs px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded font-medium transition"
            >
              Review in Approvals Queue →
            </a>
          </div>
          <p className="text-xs text-amber-200/90 leading-relaxed">
            Execution suspended at super-step boundary `human_approval_gate_node`. Checkpoint snapshot persisted to PostgreSQL.
          </p>
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
          <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
            Execution Event Stream
          </h2>
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
