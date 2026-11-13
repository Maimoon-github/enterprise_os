import { asObject, crmFetch } from "./crm-utils";

type Data = Record<string, unknown>;
type Entry = { at: number; promise: Promise<Data> };

/** How long a prefetched workspace may sit unused before it is considered stale. */
const TTL_MS = 30_000;
const cache = new Map<string, Entry>();

/**
 * Starts loading a record workspace before the record page is opened — from
 * a row the pointer is resting on — so that by the time the page mounts the
 * response is already in flight or here. The record page takes it once; a
 * later reload (after a mutation) always goes to the network.
 */
export function prefetchRecordWorkspace(recordId: string) {
  if (!recordId) return;
  const hit = cache.get(recordId);
  if (hit && Date.now() - hit.at < TTL_MS) return;
  const promise = crmFetch(`/records/${recordId}`).then(asObject);
  cache.set(recordId, { at: Date.now(), promise });
  promise.catch(() => { if (cache.get(recordId)?.promise === promise) cache.delete(recordId); });
}

export function takeRecordWorkspace(recordId: string): Promise<Data> | null {
  const hit = cache.get(recordId);
  cache.delete(recordId);
  return hit && Date.now() - hit.at < TTL_MS ? hit.promise : null;
}
