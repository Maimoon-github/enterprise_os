-- AlterEnum
ALTER TYPE "LeadStatus" ADD VALUE 'FAILED';

-- AlterTable
ALTER TABLE "Lead" ADD COLUMN "inviteRetryCount" INTEGER NOT NULL DEFAULT 0;
