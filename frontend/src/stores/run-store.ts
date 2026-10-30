import { create } from "zustand";
import { GraphNodeStatus, RunStreamEvent } from "@/types/graph";

export interface NodeState {
  node: string;
  step: number;
  status: GraphNodeStatus;
}

interface RunStore {
  activeRunId: string | null;
  nodeStates: Record<string, NodeState>;
  events: RunStreamEvent[];
  activeToolCall: { tool: string; args: Record<string, unknown> } | null;
  interruptedPayload: Record<string, unknown> | null;
  setActiveRunId: (id: string | null) => void;
  updateNodeState: (node: string, state: NodeState) => void;
  addEvent: (event: RunStreamEvent) => void;
  setActiveToolCall: (toolCall: { tool: string; args: Record<string, unknown> } | null) => void;
  setInterruptedPayload: (payload: Record<string, unknown> | null) => void;
  reset: () => void;
}

export const useRunStore = create<RunStore>((set) => ({
  activeRunId: null,
  nodeStates: {},
  events: [],
  activeToolCall: null,
  interruptedPayload: null,
  setActiveRunId: (id) => set({ activeRunId: id }),
  updateNodeState: (node, state) =>
    set((prev) => ({
      nodeStates: { ...prev.nodeStates, [node]: state },
    })),
  addEvent: (event) =>
    set((prev) => ({
      events: [...prev.events, event],
    })),
  setActiveToolCall: (toolCall) => set({ activeToolCall: toolCall }),
  setInterruptedPayload: (payload) => set({ interruptedPayload: payload }),
  reset: () =>
    set({
      activeRunId: null,
      nodeStates: {},
      events: [],
      activeToolCall: null,
      interruptedPayload: null,
    }),
}));
