/**
 * Puts follow-up drafts written before their sequence's "Send follow-ups
 * automatically" was switched on onto the automatic path, so the sender
 * (src/lib/crm/autoFollowUps.ts) works through them at its usual pace — one
 * per sending account per 30 minutes, inside the account's hours — instead
 * of them waiting in Action required.
 *
 *   bun run --conditions=react-server scripts/queue-existing-crm-follow-ups.ts           # dry run
 *   bun run --conditions=react-server scripts/queue-existing-crm-follow-ups.ts --apply   # queue them
 *
 * Only what queueAutoFollowUpInTransaction accepts is queued: a follow-up of a
 * sequence that sends automatically, on a live run and the record's current
 * context, whose lead's latest reply was answered from the CRM. A follow-up
 * on an unanswered reply stays with a person, and the dry run lists it.
 * Oldest drafts are queued first. Re-running queues nothing twice.
 */
import { sql } from "drizzle-orm";

const apply = process.argv.includes("--apply");

const { db } = await import("@/lib/db");
const { runInOrganization } = await import("@/lib/tenancy/scope");
const { withCrmTransaction } = await import("@/lib/crm/repository");
const { queueAutoFollowUpInTransaction } = await import("@/lib/crm/autoFollowUps");

type Candidate = {
  draft_id: string;
  organization_id: string;
  channel: string;
  account_ref: string;
  drafted_at: Date;
  person: string | null;
  answered_from_crm: boolean;
};

// Platform-wide on purpose: this finds which organizations have drafts to queue.
const candidates = await db.execute<Candidate>(sql`
  select d.id as draft_id, r.organization_id, c.channel, c.account_ref, d.created_at as drafted_at,
         coalesce(p.full_name, p.email, p.linkedin_url) as person,
         exists (
           select 1 from crm_conversation_messages m
           join crm_conversations mc on mc.id = m.conversation_id
           where mc.crm_record_id = r.id and m.direction = 'outbound' and m.sent_at >= inbound.sent_at
         ) as answered_from_crm
  from crm_drafts d
  join crm_records r on r.id = d.crm_record_id
  join people p on p.id = r.person_id
  join crm_conversations c on c.id = d.conversation_id
  join crm_sequence_step_runs sr on sr.id = d.sequence_step_run_id
  join crm_sequence_steps st on st.id = sr.sequence_step_id
  join crm_sequence_runs run on run.id = sr.sequence_run_id
  join crm_sequences s on s.id = run.sequence_id
  join crm_conversation_messages inbound on inbound.id = r.latest_inbound_message_id
  where d.status = 'awaiting_review' and d.auto_send_at is null
    and st.step_type = 'follow_up' and s.auto_send_follow_ups
    and run.status = 'active' and sr.status = 'awaiting_review'
    and r.context_version = d.expected_context_version
    and r.workflow_state in ('action_required', 'waiting')
  order by d.created_at asc
`);

const queueable = candidates.filter((row) => row.answered_from_crm);
const unanswered = candidates.filter((row) => !row.answered_from_crm);

console.log(`${apply ? "Queueing" : "Dry run:"} ${queueable.length} follow-up draft(s) for automatic sending.`);
const perAccount = new Map<string, number>();
for (const row of queueable) perAccount.set(`${row.channel} ${row.account_ref}`, (perAccount.get(`${row.channel} ${row.account_ref}`) ?? 0) + 1);
for (const [account, count] of [...perAccount].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${account}: ${count} — about ${Math.ceil(((count - 1) * 30) / 60)} h of sending hours at one per 30 min`);
}
if (unanswered.length) {
  console.log(`\nLeft in Action required: ${unanswered.length} whose lead's latest reply was never answered from the CRM:`);
  for (const row of unanswered) console.log(`  ${row.channel} ${row.person ?? "?"} (draft ${row.draft_id})`);
}

if (apply) {
  // Oldest first, one second apart, so the sender's oldest-first order holds.
  const base = Date.now();
  let queued = 0;
  let skipped = 0;
  for (const [index, row] of queueable.entries()) {
    const ok = await runInOrganization(row.organization_id, () => withCrmTransaction((tx) => queueAutoFollowUpInTransaction(tx, {
      draftId: row.draft_id,
      at: new Date(base + index * 1_000),
      actorType: "system",
      reason: "sequence_switched_on_after_drafting",
    })));
    if (ok) queued += 1;
    else skipped += 1;
  }
  console.log(`\nQueued ${queued}; ${skipped} changed since the dry run and were left as they are.`);
}
process.exit(0);
