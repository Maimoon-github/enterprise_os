// Session-persisted overlay for static (server-less) mode.
//
// In static mode there is no backend to write to, so competitor create/update/
// delete are applied to a localStorage-backed overlay on top of the baked
// `competitors.json`. Edits survive reloads within the browser but reset when
// the user clears storage (or when a fresh data snapshot ships). This keeps the
// Settings CRUD genuinely interactive in the demo without any server cost.

import type { Competitor, CompetitorCreate, CompetitorUpdate } from "./types";

const KEY = "compete:static-overlay:v1";

interface Overlay {
  created: Competitor[];
  updated: Record<string, CompetitorUpdate>;
  deleted: string[];
}

const EMPTY: Overlay = { created: [], updated: {}, deleted: [] };

function load(): Overlay {
  if (typeof window === "undefined") return { ...EMPTY };
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...EMPTY, ...(JSON.parse(raw) as Overlay) } : { ...EMPTY };
  } catch {
    return { ...EMPTY };
  }
}

function save(o: Overlay): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(o));
  } catch {
    /* storage full / disabled - overlay is best-effort */
  }
}

export function slugify(name: string): string {
  return (
    name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "competitor"
  );
}

/** Merge the baked competitor list with the session overlay. */
export function applyOverlay(base: Competitor[]): Competitor[] {
  const o = load();
  const deleted = new Set(o.deleted);
  const merged = base
    .filter((c) => !deleted.has(c.id))
    .map((c) => (o.updated[c.id] ? { ...c, ...o.updated[c.id] } : c));
  // Created competitors (also honoring later updates/deletes of them).
  for (const c of o.created) {
    if (deleted.has(c.id)) continue;
    merged.unshift(o.updated[c.id] ? { ...c, ...o.updated[c.id] } : c);
  }
  return merged;
}

export function createCompetitor(base: Competitor[], body: CompetitorCreate): Competitor {
  const o = load();
  const existing = new Set([...base.map((c) => c.id), ...o.created.map((c) => c.id)]);
  let id = body.id?.trim() || slugify(body.name);
  while (existing.has(id)) id = `${id}-2`;
  const competitor: Competitor = {
    id,
    name: body.name,
    domain: body.domain ?? null,
    industry: body.industry ?? null,
    tier: body.tier ?? 2,
    tracked_urls: body.tracked_urls ?? [],
    tracked_url_count: body.tracked_urls?.length ?? 0,
    signal_count: 0,
    high_significance_count: 0,
    last_signal_at: null,
  };
  o.created.unshift(competitor);
  save(o);
  return competitor;
}

export function updateCompetitor(
  base: Competitor[],
  id: string,
  body: CompetitorUpdate,
): Competitor {
  const o = load();
  o.updated[id] = { ...o.updated[id], ...body };
  if (body.tracked_urls) {
    // keep the derived count consistent with the edited urls
    o.updated[id] = { ...o.updated[id], tracked_urls: body.tracked_urls };
  }
  save(o);
  const merged = applyOverlay(base).find((c) => c.id === id);
  return merged ?? createCompetitor(base, { name: id, ...body });
}

export function deleteCompetitor(id: string): void {
  const o = load();
  if (!o.deleted.includes(id)) o.deleted.push(id);
  // also drop it from created/updated so it fully disappears
  o.created = o.created.filter((c) => c.id !== id);
  delete o.updated[id];
  save(o);
}
