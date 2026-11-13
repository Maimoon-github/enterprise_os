-- DropForeignKey
ALTER TABLE "Lead" DROP CONSTRAINT "Lead_linkedinAccountId_fkey";

-- AlterTable
ALTER TABLE "Lead" ALTER COLUMN "linkedinAccountId" DROP NOT NULL;

-- AddForeignKey
ALTER TABLE "Lead" ADD CONSTRAINT "Lead_linkedinAccountId_fkey" FOREIGN KEY ("linkedinAccountId") REFERENCES "LinkedInAccount"("id") ON DELETE SET NULL ON UPDATE CASCADE;
