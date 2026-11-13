-- Allow the same LinkedIn profile to be a Lead in more than one campaign,
-- and the same person to have a Connection per (person, sending account)
-- instead of one Connection system-wide.
--
-- Note: campaignId and linkedinAccountId are nullable columns. Postgres
-- treats each NULL as a distinct value in a unique index, so two Leads with
-- the same linkedinUrl and campaignId = NULL (no campaign) will NOT collide,
-- and likewise for Connections with linkedinAccountId = NULL. This matches
-- existing "no campaign assigned yet" / "account not resolved yet" behavior
-- and is an accepted, unchanged edge case.

-- DropIndex
DROP INDEX "Lead_linkedinUrl_key";

-- DropIndex
DROP INDEX "Connection_providerId_key";

-- CreateIndex
CREATE INDEX "Lead_linkedinUrl_idx" ON "Lead"("linkedinUrl");

-- CreateIndex
CREATE INDEX "Lead_providerId_idx" ON "Lead"("providerId");

-- CreateIndex
CREATE UNIQUE INDEX "Lead_linkedinUrl_campaignId_key" ON "Lead"("linkedinUrl", "campaignId");

-- CreateIndex
CREATE UNIQUE INDEX "Connection_providerId_linkedinAccountId_key" ON "Connection"("providerId", "linkedinAccountId");
