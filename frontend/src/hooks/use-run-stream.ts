"use client";

import { useEffect, useState } from "react";
import { subscribeToRunStream } from "@/lib/sse/run-stream";
import { useRunStore } from "@/stores/run-store";
import { RunStreamEvent } from "@/types/graph";

export function useRunStream(runId?: string) {
  const [events, setEvents] = useState<RunStreamEvent[]>([]);
  const updateNodeState = useRunStore((s) => s.updateNodeState);
  const setActiveRunId = useRunStore((s) => s.setActiveRunId);
  const setActiveToolCall = useRunStore((s) => s.setActiveToolCall);
  const setInterruptedPayload = useRunStore((s) => s.setInterruptedPayload);
  const setRunStatus = useRunStore((s) => s.setRunStatus);
  const setErrorMessage = useRunStore((s) => s.setErrorMessage);
  const addStoreEvent = useRunStore((s) => s.addEvent);

  useEffect(() => {
    if (!runId) return;
    setActiveRunId(runId);
    setRunStatus("running");

    const unsubscribe = subscribeToRunStream(
      runId,
      (ev) => {
        setEvents((prev) => [...prev, ev]);
        addStoreEvent(ev);

        if (ev.event === "node_start" || ev.event === "node_transition") {
          if (ev.data?.node) {
            updateNodeState(ev.data.node, {
              node: ev.data.node,
              step: ev.data.step || 1,
              status: "executing",
            });
          }
        } else if (ev.event === "tool_call") {
          if (ev.data?.tool) {
            setActiveToolCall({
              tool: ev.data.tool,
              args: ev.data.args || {},
            });
          }
        } else if (ev.event === "interrupt") {
          if (ev.data?.node) {
            updateNodeState(ev.data.node, {
              node: ev.data.node,
              step: ev.data.step || 1,
              status: "interrupted",
            });
          }
          if (ev.data?.payload) {
            setInterruptedPayload(ev.data.payload);
          }
          setRunStatus("interrupted");
        } else if (ev.event === "node_finish") {
          if (ev.data?.node) {
            updateNodeState(ev.data.node, {
              node: ev.data.node,
              step: ev.data.step || 1,
              status: "completed",
            });
          }
        } else if (ev.event === "complete") {
          const finalStatus = (ev.data?.status as string) || "completed";
          setRunStatus(finalStatus);
          if (ev.data?.error) {
            setErrorMessage(String(ev.data.error));
          }
        }
      },
      (err) => {
        console.error("SSE run stream error:", err);
      }
    );

    return () => unsubscribe();
  }, [
    runId,
    setActiveRunId,
    updateNodeState,
    setActiveToolCall,
    setInterruptedPayload,
    setRunStatus,
    setErrorMessage,
    addStoreEvent,
  ]);

  return { events };
}
