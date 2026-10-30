"use client";

import { useEffect, useState } from "react";
import { subscribeToRunStream } from "@/lib/sse/run-stream";

export function useRunStream(runId?: string) {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    if (!runId) return;
    const unsubscribe = subscribeToRunStream(runId, (ev) => {
      setEvents((prev) => [...prev, ev.data]);
    });
    return () => unsubscribe();
  }, [runId]);

  return { events };
}
