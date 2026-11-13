-- CreateEnum
CREATE TYPE "CampaignType" AS ENUM ('REGULAR', 'PERSONAL');

-- AlterTable
ALTER TABLE "Campaign" ADD COLUMN     "type" "CampaignType" NOT NULL DEFAULT 'REGULAR';
