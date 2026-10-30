export function subscribeToRunStream(
  runId: string,
  onEvent: (event: { event: string; data: any }) => void,
  onError?: (err: any) => void
) {
  const eventSource = new EventSource(`http://localhost:8000/api/v1/runs/${runId}/stream`);

  eventSource.addEventListener("node_transition", (e) => {
    onEvent({ event: "node_transition", data: JSON.parse(e.data) });
  });

  eventSource.addEventListener("complete", (e) => {
    onEvent({ event: "complete", data: JSON.parse(e.data) });
    eventSource.close();
  });

  eventSource.onerror = (err) => {
    if (onError) onError(err);
    eventSource.close();
  };

  return () => eventSource.close();
}
