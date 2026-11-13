/**
 * Repairs sequence steps left on an old context version by "Skip step" or
 * "Snooze" before refreshPendingStepContextInTransaction (src/lib/crm/
 * sequences.ts). Those actions bumped the record's version but refreshed
 * only the next step, so once that step was sent the run advanced onto a
 * step that could never be drafted: its due-follow-up job failed as "CRM
 * work is stale" (and is never retried) and the record waited forever.
 *
 *   bun run --conditions=react-server scripts/repair-crm-stale-step-versions.ts           # dry run
 *   bun run --conditions=react-server scripts/repair-crm-stale-step-versions.ts --apply
 *
 * Only runs still answering the record's latest reply (same trigger message,
 * no newer inbound) are touched — exactly the runs whose drafting refused
 * the step for its version alone. Their scheduled steps take the record's
 * version, and a failed due-follow-up job for them is queued again, so the
 * CRM worker drafts the step on its next pass. Re-running changes nothing.
 * Run 29 Oct 2026: 7 runs.
 */
import postgres from "postgres";

const apply = process.argv.includes("--apply");
if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
const sql = postgres(process.env.DATABASE_URL, { ssl: process.env.DATABASE_SSL === "disable" ? false : "require", max: 1 });

try {
  await sql.begin(async (tx) => {
    const stale = await tx<{ step_run_id: string; organization_id: string; record_id: string; position: number; due_at: Date; record_version: number; step_version: number }[]>`
      select sr.id as step_run_id, r.organization_id, r.id as record_id, st.position, sr.due_at,
             r.context_version as record_version, sr.expected_context_version as step_version
      from crm_sequence_step_runs sr
      join crm_sequence_runs run on run.id = sr.sequence_run_id
      join crm_records r on r.id = run.crm_record_id
      join crm_sequence_steps st on st.id = sr.sequence_step_id
      where run.status = 'active'
        and sr.status = 'scheduled'
        and sr.expected_context_version <> r.context_version
        and r.latest_inbound_message_id = run.trigger_message_id
        and (r.last_inbound_at is null or r.last_inbound_at <= run.last_inbound_at_start)
      order by sr.due_at
      for update of sr`;
    const records = new Set(stale.map((row) => row.record_id));
    console.log(`${apply ? "Repairing" : "Dry run:"} ${stale.length} step(s) on ${records.size} record(s) with an old context version.`);
    for (const row of stale) {
      console.log(`  record ${row.record_id} step ${row.position} (due ${row.due_at.toISOString()}): v${row.step_version} → v${row.record_version}`);
    }
    if (!apply || !stale.length) return;

    const ids = stale.map((row) => row.step_run_id);
    const updated = await tx`
      update crm_sequence_step_runs sr
      set expected_context_version = r.context_version, updated_at = now()
      from crm_sequence_runs run, crm_records r
      where sr.id in ${tx(ids)} and run.id = sr.sequence_run_id and r.id = run.crm_record_id`;
    // Same reset requeueFailedCrmJob applies (src/lib/crm/queue.ts).
    const requeued = await tx`
      update crm_jobs
      set status = 'queued', attempts = 0, run_after = now(), locked_at = null, locked_by = null,
          started_at = null, completed_at = null, failed_at = null, last_error = null, updated_at = now()
      where kind = 'due_followup_draft' and status = 'failed' and entity_id in ${tx(ids)}`;
    console.log(`\nUpdated ${updated.count} step(s); queued ${requeued.count} failed drafting job(s) again.`);
  });
} finally {
  await sql.end();
}
