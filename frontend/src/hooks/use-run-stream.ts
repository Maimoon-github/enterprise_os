"use client";

import { useEffect, useState } from "react";
import { subscribeToRunStream } from "@/lib/sse/run-stream";
import { useRunStore } from "@/stores/run-store";

export function useRunStream(runId?: string) {
  const [events, setEvents] = useState<any[]>([]);
  const updateNodeState = useRunStore((s) => s.updateNodeState);
  const setActiveRunId = useRunStore((s) => s.setActiveRunId);

  useEffect(() => {
    if (!runId) return;
    setActiveRunId(runId);
    const unsubscribe = subscribeToRunStream(runId, (ev) => {
      setEvents((prev) => [...prev, ev.data]);
      if (ev.event === "node_transition" && ev.data?.node) {
        updateNodeState(ev.data.node, {
          node: ev.data.node,
          step: ev.data.step || 1,
          status: ev.data.status || "executing",
        });
      }
    });
    return () => unsubscribe();
  }, [runId, setActiveRunId, updateNodeState]);

  return { events };
}
