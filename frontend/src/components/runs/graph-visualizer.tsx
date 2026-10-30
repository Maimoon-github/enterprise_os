import { NodeState } from "@/stores/run-store";

interface GraphVisualizerProps {
  currentNode?: string;
  nodeStates?: Record<string, NodeState>;
}

export function GraphVisualizer({
  currentNode,
  nodeStates = {},
}: GraphVisualizerProps) {
  const dagNodes = [
    { id: "supervisor_router", label: "Supervisor Router", type: "supervisor" },
    { id: "research_strategy", label: "Research Strategy", type: "subgraph" },
    { id: "campaign_creative", label: "Campaign Creative", type: "subgraph" },
    { id: "prepare_publish_payload_node", label: "Payload Stager", type: "gate" },
    { id: "human_approval_gate_node", label: "Approval Gate", type: "interrupt" },
    { id: "execute_platform_publish_node", label: "Platform Fanout", type: "fanout" },
    { id: "closed_loop_eval", label: "Closed Loop Eval", type: "eval" },
  ];

  const getNodeColor = (id: string, isCurrent: boolean) => {
    const state = nodeStates[id];
    const status = state?.status;

    if (status === "interrupted" || id === "human_approval_gate_node" && isCurrent) {
      return "border-amber-500 bg-amber-950/60 text-amber-300 animate-pulse";
    }
    if (status === "executing" || isCurrent) {
      return "border-indigo-500 bg-indigo-950/60 text-white ring-2 ring-indigo-500/40";
    }
    if (status === "completed") {
      return "border-emerald-700 bg-emerald-950/40 text-emerald-300";
    }
    return "border-slate-800 bg-slate-900 text-slate-400";
  };

  return (
    <div className="flex items-center gap-2 p-4 bg-slate-950 border border-slate-800 rounded-xl overflow-x-auto text-xs scrollbar-thin">
      {dagNodes.map((n, i) => {
        const isCurrent = currentNode === n.id;
        const colorClass = getNodeColor(n.id, isCurrent);

        return (
          <div key={n.id} className="flex items-center gap-2 shrink-0">
            <div className={`px-3 py-2.5 rounded-lg border font-mono transition-all duration-200 ${colorClass}`}>
              <div className="font-semibold">{n.label}</div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">
                {nodeStates[n.id]?.status || (isCurrent ? "active" : "idle")}
              </div>
            </div>
            {i < dagNodes.length - 1 && (
              <span className="text-slate-600 font-bold px-0.5">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
