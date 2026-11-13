-- AlterEnum
ALTER TYPE "MessageType" ADD VALUE 'FOLLOW_UP_3';

-- AlterEnum
ALTER TYPE "LeadStatus" ADD VALUE 'FOLLOW_UP_3_SENT';

-- AlterTable
ALTER TABLE "Lead" ADD COLUMN "followUp3Message" TEXT,
ADD COLUMN "followUp3SentAt" TIMESTAMP(3);
