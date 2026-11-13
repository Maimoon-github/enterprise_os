"use client";

import { useEffect, useRef } from "react";

/**
 * Calls `callback` every `intervalMs` while the tab is visible, and once
 * straight away when the tab becomes visible again. A hidden tab never polls,
 * so a forgotten Messages tab does not keep hitting the API.
 */
export function useVisiblePolling(callback: () => void, intervalMs: number, enabled = true) {
  const latest = useRef(callback);
  useEffect(() => {
    latest.current = callback;
  });

  useEffect(() => {
    if (!enabled) return;
    const tick = () => {
      if (document.visibilityState === "visible") latest.current();
    };
    const interval = setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [intervalMs, enabled]);
}

/** How often the Messages list and open threads refresh. */
export const WHATSAPP_POLL_INTERVAL_MS = 10_000;
