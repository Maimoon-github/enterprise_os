/**
 * Leaves the seeded organization at rest: nothing queued for a worker to pick
 * up, nothing scheduled in the past for the CRM's follow-up sweep to turn into
 * a failed AI job on the first boot of a server that is not in DEMO_MODE.
 */

import { and, inArray, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { crmJobs } from "@/lib/crm/schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import type { DemoContext } from "./context";

export async function finalizeDemo(ctx: DemoContext): Promise<void> {
  // Classification and drafting jobs queued by ingest: the seed already did their work.
  await db.delete(crmJobs).where(and(inOrg(crmJobs), inArray(crmJobs.status, ["queued"])));

  // Follow-ups due before now would be drafted by the worker on boot; push
  // them into the next few days. Step runs are scoped through their run.
  await db.execute(sql`
    update crm_sequence_step_runs sr
       set due_at = ${ctx.now.toISOString()}::timestamptz + interval '2 hours' + random() * interval '3 days'
      from crm_sequence_runs r
     where r.id = sr.sequence_run_id
       and r.organization_id = ${currentOrganizationId()}
       and sr.status = 'scheduled'
       and sr.due_at < ${ctx.now.toISOString()}::timestamptz`);
}
