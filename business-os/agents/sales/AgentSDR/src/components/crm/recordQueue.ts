import { useSyncExternalStore } from "react";

/**
 * The list a record pop-up was opened from, so the pop-up can step to the
 * previous and next lead without the reader closing it to find the next row.
 *
 * The list under the pop-up is never unmounted (see CrmRecordModal), so it
 * publishes its rows here as they change — loaded pages, a row swapped after
 * an edit, a row dropped once it is handled — and the pop-up reads them. Only
 * one list is on screen at a time; a page with no list publishes nothing and
 * the pop-up shows no stepping controls.
 */
export type QueueItem = { id: string; name: string; avatarUrl: string | null; channel: string };
export type RecordQueue = { items: QueueItem[]; hasMore: boolean; loadMore?: () => void };

let current: RecordQueue | null = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function publishRecordQueue(queue: RecordQueue | null) {
  current = queue;
  for (const listener of listeners) listener();
}

/** Clears the queue only if it is still the one this list published. */
export function withdrawRecordQueue(queue: RecordQueue | null) {
  if (queue && current === queue) publishRecordQueue(null);
}

export function useRecordQueue(): RecordQueue | null {
  return useSyncExternalStore(subscribe, () => current, () => null);
}

/**
 * Replies typed into the pop-up and not yet saved or sent, by record. Stepping
 * to another lead unmounts the composer, so the pop-up asks first rather than
 * dropping someone's edits.
 */
const unsavedReplies = new Set<string>();

export function setUnsavedReply(recordId: string, unsaved: boolean) {
  if (!recordId) return;
  if (unsaved) unsavedReplies.add(recordId); else unsavedReplies.delete(recordId);
}

export function hasUnsavedReply(recordId: string) {
  return unsavedReplies.has(recordId);
}
