-- CreateTable
CREATE TABLE "CampaignAccount" (
    "campaignId" TEXT NOT NULL,
    "linkedinAccountId" TEXT NOT NULL,
    CONSTRAINT "CampaignAccount_pkey" PRIMARY KEY ("campaignId","linkedinAccountId")
);

-- AddForeignKey
ALTER TABLE "CampaignAccount" ADD CONSTRAINT "CampaignAccount_campaignId_fkey" FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CampaignAccount" ADD CONSTRAINT "CampaignAccount_linkedinAccountId_fkey" FOREIGN KEY ("linkedinAccountId") REFERENCES "LinkedInAccount"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AlterTable (drop old single-account FK)
ALTER TABLE "Campaign" DROP COLUMN IF EXISTS "linkedinAccountId";
