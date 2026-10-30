import { RunStreamEvent, RunStreamEventType } from "@/types/graph";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function subscribeToRunStream(
  runId: string,
  onEvent: (event: RunStreamEvent) => void,
  onError?: (err: unknown) => void
): () => void {
  if (typeof window === "undefined" || !runId) {
    return () => {};
  }

  const url = `${API_BASE}/runs/${encodeURIComponent(runId)}/stream`;
  const eventSource = new EventSource(url);

  const eventTypes: RunStreamEventType[] = [
    "node_start",
    "node_transition",
    "tool_call",
    "interrupt",
    "node_finish",
    "complete",
  ];

  eventTypes.forEach((type) => {
    eventSource.addEventListener(type, (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data);
        onEvent({ event: type, data: parsed });
      } catch {
        onEvent({ event: type, data: { raw: e.data } });
      }
      if (type === "complete") {
        eventSource.close();
      }
    });
  });

  eventSource.onerror = (err) => {
    if (onError) onError(err);
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}
