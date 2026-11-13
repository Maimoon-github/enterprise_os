/** Live smoke test for direct canonical campaign references. Every write rolls back. */
// Runs in ORGANIZATION_ID, or the initial organization when it is unset.
import { eq } from "drizzle-orm";
import { db } from "../src/lib/db";
import { campaigns as linkedinCampaigns, leads as linkedinLeads } from "../src/lib/linkedin/schema";
import { people } from "../src/lib/leads/schema";
import { outreachCampaigns, outreachLeads } from "../src/lib/outreach/schema";
import { upsertPerson } from "../src/lib/leads/records";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import { runScriptInOrganization } from "./lib/organization";

const marker = `canonical-smoke-${Date.now()}`;
const rollback = new Error("ROLLBACK_CANONICAL_SMOKE_TEST");

async function main() {
  try {
    await db.transaction(async (tx) => {
      const person = await upsertPerson(tx, {
        email: `${marker}@example.test`,
        linkedinUrl: marker,
        fullName: "Canonical Smoke Test",
        source: "test:rollback",
      });

      const [emailCampaign] = await tx.insert(outreachCampaigns).values({ organizationId: currentOrganizationId(), name: marker }).returning();
      await tx.insert(outreachLeads).values({ personId: person.id, campaignId: emailCampaign.id }).returning();

      const linkedinCampaignId = `${marker}-li`;
      await tx.insert(linkedinCampaigns).values({ organizationId: currentOrganizationId(), id: linkedinCampaignId, name: marker, updatedAt: new Date() });
      await tx.insert(linkedinLeads).values({ organizationId: currentOrganizationId(), personId: person.id, campaignId: linkedinCampaignId, updatedAt: new Date() }).returning();

      const [emailLink] = await tx.select().from(outreachLeads).where(eq(outreachLeads.personId, person.id)).limit(1);
      const [linkedinLink] = await tx.select().from(linkedinLeads).where(eq(linkedinLeads.personId, person.id)).limit(1);
      if (!emailLink || !linkedinLink) throw new Error("Direct person references were not created");
      throw rollback;
    });
  } catch (error) {
    if (error !== rollback) throw error;
  }

  const residue = await db.select({ id: people.id }).from(people).where(eq(people.email, `${marker}@example.test`));
  if (residue.length) throw new Error("Rollback failed: smoke-test person remains");
  console.log("Canonical Email + LinkedIn direct-reference smoke test passed; all writes rolled back.");
}

runScriptInOrganization(main)
  .catch((error) => {
  console.error(error);
  process.exit(1);
});
