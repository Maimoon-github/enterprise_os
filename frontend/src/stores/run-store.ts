import { create } from "zustand";

interface NodeState {
  node: string;
  step: number;
  status: "pending" | "executing" | "completed" | "interrupted" | "failed";
}

interface RunStore {
  activeRunId: string | null;
  nodeStates: Record<string, NodeState>;
  setActiveRunId: (id: string | null) => void;
  updateNodeState: (node: string, state: NodeState) => void;
  reset: () => void;
}

export const useRunStore = create<RunStore>((set) => ({
  activeRunId: null,
  nodeStates: {},
  setActiveRunId: (id) => set({ activeRunId: id }),
  updateNodeState: (node, state) =>
    set((prev) => ({
      nodeStates: { ...prev.nodeStates, [node]: state },
    })),
  reset: () => set({ activeRunId: null, nodeStates: {} }),
}));
