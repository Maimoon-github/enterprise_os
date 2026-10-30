export type GraphNodeType =
  | "supervisor"
  | "subgraph"
  | "approval_gate"
  | "fanout_worker"
  | "revision_node";

export type GraphNodeStatus =
  | "idle"
  | "pending"
  | "running"
  | "executing"
  | "completed"
  | "interrupted"
  | "failed";

export interface GraphNode {
  id: string;
  name: string;
  type: GraphNodeType;
  status: GraphNodeStatus;
  step?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  condition?: string;
}

export type RunStreamEventType =
  | "node_start"
  | "node_transition"
  | "tool_call"
  | "interrupt"
  | "node_finish"
  | "complete";

export interface RunStreamEvent {
  event: RunStreamEventType;
  data: {
    run_id?: string;
    thread_id?: string;
    node?: string;
    step?: number;
    status?: string;
    tool?: string;
    args?: Record<string, unknown>;
    payload?: Record<string, unknown>;
    reason?: string;
    error?: string;
    raw?: string;
    [key: string]: unknown;
  };
}
