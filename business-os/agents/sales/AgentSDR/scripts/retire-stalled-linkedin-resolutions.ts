/**
 * Settles the Leads left stranded by the old profile-resolution retry budget.
 *
 * Resolution used to allow 10 attempts and, on the tenth, simply stopped
 * matching the claim query — the Lead stayed PENDING forever with no status
 * anyone could see. The budget is now MAX_LEAD_RETRIES, so every row already
 * at or above it is unreachable. This gives each one an outcome:
 *
 *   - Leads that only failed because a bare vanity slug starting with "-" or
 *     "_" was rejected by normalizeLinkedinSlug are now resolvable, so their
 *     retry counters are cleared for a fresh attempt.
 *   - Everything else at or over the budget (locked/deleted profiles, opaque
 *     member URNs with no public identity) becomes FAILED.
 *
 * Dry run:
 *   bun --conditions=react-server scripts/retire-stalled-linkedin-resolutions.ts
 * Apply:
 *   bun --conditions=react-server scripts/retire-stalled-linkedin-resolutions.ts --apply
 */
import { and, eq, gte, inArray, isNotNull } from "drizzle-orm";
import { db } from "../src/lib/db";
import { leads } from "../src/lib/linkedin/schema";
import { publicSlugFromSourceIdentifier } from "../src/lib/leads/identity";
import { MAX_LEAD_RETRIES } from "../src/lib/linkedin/inviteRetry";

const apply = process.argv.includes("--apply");

async function main() {
  const stalled = await db
    .select({
      id: leads.id,
      source: leads.sourceLinkedinIdentifier,
      retryCount: leads.resolveRetryCount,
      lastError: leads.resolveLastError,
    })
    .from(leads)
    .where(and(
      eq(leads.status, "PENDING"),
      isNotNull(leads.sourceLinkedinIdentifier),
      gte(leads.resolveRetryCount, MAX_LEAD_RETRIES),
    ));

  // Only a slug rejected by the old leading-character rule earns a retry; a
  // 422 or a URN with no public profile fails again for the same reason.
  const retryable = stalled.filter(
    (lead) =>
      lead.lastError?.includes("no canonical public LinkedIn identifier") &&
      publicSlugFromSourceIdentifier(lead.source) !== null,
  );
  const retryableIds = new Set(retryable.map((lead) => lead.id));
  const failing = stalled.filter((lead) => !retryableIds.has(lead.id));

  console.log(`Stalled at or over ${MAX_LEAD_RETRIES} attempt(s): ${stalled.length}`);
  console.log(`  → reset for another attempt: ${retryable.length}`);
  for (const lead of retryable) console.log(`     ${lead.source} (${lead.retryCount} attempts)`);
  console.log(`  → mark FAILED: ${failing.length}`);
  for (const lead of failing) {
    console.log(`     ${lead.source} (${lead.retryCount} attempts) — ${lead.lastError?.slice(0, 80) ?? "no error recorded"}`);
  }

  if (!apply) {
    console.log("\nDry run — pass --apply to write.");
    return;
  }

  for (const lead of retryable) {
    await db
      .update(leads)
      .set({ resolveRetryCount: 0, resolveNextAttemptAt: null, resolveLastError: null })
      .where(eq(leads.id, lead.id));
  }
  if (failing.length > 0) {
    await db
      .update(leads)
      .set({ status: "FAILED", resolveNextAttemptAt: null })
      .where(and(
        eq(leads.status, "PENDING"),
        inArray(leads.id, failing.map((lead) => lead.id)),
      ));
  }
  console.log(`\nApplied — reset ${retryable.length}, failed ${failing.length}.`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
