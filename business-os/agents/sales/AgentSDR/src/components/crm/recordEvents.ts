import { useEffect, useRef } from "react";

/**
 * A record opened in the pop-up over a list is changed there, not in the
 * list: the list's rows are client state, so a router.refresh() would not
 * touch them. The record page announces each change it makes, and a list
 * holding that record re-reads just that row — the same swap-or-drop an
 * inline edit does — so closing the pop-up lands on a list that is current.
 */
const EVENT = "crm:record-changed";

export function announceRecordChanged(recordId: string) {
  if (typeof window === "undefined" || !recordId) return;
  window.dispatchEvent(new CustomEvent<{ recordId: string }>(EVENT, { detail: { recordId } }));
}

export function useRecordChanged(onChange: (recordId: string) => void) {
  const handler = useRef(onChange);
  useEffect(() => { handler.current = onChange; });
  useEffect(() => {
    const listener = (event: Event) => {
      const recordId = (event as CustomEvent<{ recordId?: string }>).detail?.recordId;
      if (recordId) handler.current(recordId);
    };
    window.addEventListener(EVENT, listener);
    return () => window.removeEventListener(EVENT, listener);
  }, []);
}
