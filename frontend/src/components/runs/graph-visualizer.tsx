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

    if (status === "interrupted" || (id === "human_approval_gate_node" && isCurrent)) {
      return "border-bloodstone-crimson bg-glass-crimson text-bloodstone-text shadow-crimson-glow animate-pulse";
    }
    if (status === "executing" || isCurrent) {
      return "border-bloodstone-mint bg-glass-emerald text-bloodstone-text ring-2 ring-bloodstone-mint/50 shadow-bloodstone-glow";
    }
    if (status === "completed") {
      return "border-glass-specular bg-glass-base text-bloodstone-mint shadow-specular-inset";
    }
    return "border-glass-subtle bg-glass-base text-bloodstone-text-muted";
  };

  return (
    <div className="flex items-center gap-2 p-4 glass-panel rounded-xl overflow-x-auto text-xs scrollbar-thin">
      {dagNodes.map((n, i) => {
        const isCurrent = currentNode === n.id;
        const colorClass = getNodeColor(n.id, isCurrent);

        return (
          <div key={n.id} className="flex items-center gap-2 shrink-0">
            <div className={`px-3 py-2.5 rounded-lg border font-mono transition-all duration-normal ease-settle ${colorClass}`}>
              <div className="font-semibold">{n.label}</div>
              <div className="text-[10px] text-bloodstone-text-dim uppercase tracking-wider mt-0.5">
                {nodeStates[n.id]?.status || (isCurrent ? "active" : "idle")}
              </div>
            </div>
            {i < dagNodes.length - 1 && (
              <span className="text-bloodstone-mint/40 font-bold px-0.5">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
