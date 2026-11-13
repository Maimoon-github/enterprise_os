import "server-only";

import { sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { isDemoMode } from "./mode";

/**
 * Keeps the demo current. The seed places every timestamp relative to the
 * moment it ran and records that moment as the organization's `clock`
 * (organizations.metadata). Each day after, this moves every date and
 * timestamp in the database forward by the whole days that have passed —
 * so "replied 2 days ago" stays 2 days ago, the analytics range keeps its
 * data, and scheduled follow-ups stay in the future.
 *
 * Whole days only, because `date` columns cannot move by part of one.
 *
 * It rewrites EVERY table, so it refuses unless DEMO_MODE is on and every
 * organization in the database is a seeded demo one. Auth bookkeeping
 * (sessions, verifications, credential accounts) is left alone. The CRM's
 * history tables are append-only by trigger, so the shift runs with
 * session_replication_role = replica, which needs a superuser — true of the
 * demo's own Postgres container. Anywhere else it logs and does nothing.
 */

const DAY_MS = 86_400_000;
const SKIP_TABLES = new Set(["sessions", "verifications", "accounts"]);
const CHECK_EVERY_MS = 60 * 60 * 1000;

type DemoClock = { organizationId: string; clock: Date };

async function readClock(): Promise<DemoClock | null> {
  const rows = (await db.execute(sql`select id, metadata from organizations`)) as unknown as { id: string; metadata: string | null }[];
  if (rows.length === 0) return null;
  let found: DemoClock | null = null;
  for (const row of rows) {
    let meta: { demo?: unknown; clock?: unknown } = {};
    try {
      meta = row.metadata ? JSON.parse(row.metadata) : {};
    } catch {
      return null;
    }
    // A single organization that is not a seeded demo means real data: never touch it.
    if (meta.demo !== true) return null;
    if (typeof meta.clock === "string" && !Number.isNaN(Date.parse(meta.clock))) {
      const clock = new Date(meta.clock);
      if (!found || clock < found.clock) found = { organizationId: row.id, clock };
    }
  }
  return found;
}

/** Moves the demo forward by the whole days since its clock. Returns the days moved. */
export async function advanceDemoClock(now = new Date()): Promise<number> {
  if (!isDemoMode()) return 0;
  const state = await readClock();
  if (!state) return 0;
  const days = Math.floor((now.getTime() - state.clock.getTime()) / DAY_MS);
  if (days < 1) return 0;

  return db.transaction(async (tx) => {
    // One instance at a time; a second waits, re-reads and finds nothing to do.
    await tx.execute(sql`select pg_advisory_xact_lock(hashtext('agentsdr:demo-clock'))`);
    const fresh = await readClock();
    if (!fresh) return 0;
    const n = Math.floor((now.getTime() - fresh.clock.getTime()) / DAY_MS);
    if (n < 1) return 0;

    await tx.execute(sql`set local session_replication_role = replica`);
    const columns = (await tx.execute(sql`
      select c.table_name, c.column_name
        from information_schema.columns c
        join information_schema.tables t on t.table_schema = c.table_schema and t.table_name = c.table_name
       where c.table_schema = 'public'
         and t.table_type = 'BASE TABLE'
         and c.data_type in ('timestamp with time zone', 'timestamp without time zone', 'date')
         and c.is_generated = 'NEVER'
       order by c.table_name, c.ordinal_position`)) as unknown as { table_name: string; column_name: string }[];

    const byTable = new Map<string, string[]>();
    for (const { table_name, column_name } of columns) {
      if (SKIP_TABLES.has(table_name)) continue;
      byTable.set(table_name, [...(byTable.get(table_name) ?? []), column_name]);
    }
    const interval = sql.raw(`interval '${n} days'`);
    for (const [table, cols] of byTable) {
      const sets = sql.join(
        cols.map((col) => sql`${sql.identifier(col)} = ${sql.identifier(col)} + ${interval}`),
        sql`, `,
      );
      await tx.execute(sql`update ${sql.identifier(table)} set ${sets}`);
    }

    const next = new Date(fresh.clock.getTime() + n * DAY_MS).toISOString();
    await tx.execute(sql`
      update organizations
         set metadata = jsonb_set(coalesce(metadata, '{}')::jsonb, '{clock}', to_jsonb(${next}::text))::text
       where metadata is not null and (metadata::jsonb ->> 'demo') = 'true'`);
    return n;
  });
}

let started = false;

/** Called once at boot in DEMO_MODE (src/instrumentation.ts): now, then hourly. */
export function startDemoClock(): void {
  if (started || !isDemoMode()) return;
  started = true;
  const tick = () =>
    advanceDemoClock()
      .then((days) => {
        if (days > 0) console.log(`[demo] moved the demo forward ${days} day${days === 1 ? "" : "s"}`);
      })
      .catch((error) => console.error("[demo] could not move the demo clock forward", error));
  void tick();
  setInterval(tick, CHECK_EVERY_MS).unref?.();
}
