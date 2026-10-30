export interface GraphNode {
  id: string;
  name: string;
  type: "supervisor" | "subgraph" | "approval_gate" | "fanout_worker";
  status: "idle" | "running" | "completed" | "interrupted" | "failed";
}

export interface GraphEdge {
  source: string;
  target: string;
  condition?: string;
}
