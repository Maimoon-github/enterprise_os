const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function subscribeToRunStream(
  runId: string,
  onEvent: (event: { event: string; data: any }) => void,
  onError?: (err: any) => void
) {
  const eventSource = new EventSource(`${API_BASE}/runs/${runId}/stream`);

  eventSource.addEventListener("node_transition", (e) => {
    try {
      onEvent({ event: "node_transition", data: JSON.parse(e.data) });
    } catch {
      onEvent({ event: "node_transition", data: e.data });
    }
  });

  eventSource.addEventListener("complete", (e) => {
    try {
      onEvent({ event: "complete", data: JSON.parse(e.data) });
    } catch {
      onEvent({ event: "complete", data: e.data });
    }
    eventSource.close();
  });

  eventSource.onerror = (err) => {
    if (onError) onError(err);
    eventSource.close();
  };

  return () => eventSource.close();
}
