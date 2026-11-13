"use client";

import { useEffect } from "react";

/**
 * Reloads when the rep comes back to this tab. The recorder extension
 * switches them here the moment a WhatsApp call ends, so the call they just
 * made should be on screen then — not on the next poll.
 */
export function useRefreshOnReturn(load: () => void | Promise<void>): void {
  useEffect(() => {
    const onReturn = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onReturn);
    window.addEventListener("focus", onReturn);
    return () => {
      document.removeEventListener("visibilitychange", onReturn);
      window.removeEventListener("focus", onReturn);
    };
  }, [load]);
}
