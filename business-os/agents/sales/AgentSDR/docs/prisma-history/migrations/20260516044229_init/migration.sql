-- CreateEnum
CREATE TYPE "LeadStatus" AS ENUM ('PENDING', 'REQUEST_SENT', 'CONNECTED', 'ACCEPT_MESSAGE_SENT', 'FOLLOW_UP_1_SENT', 'FOLLOW_UP_2_SENT', 'REPLIED');

-- CreateEnum
CREATE TYPE "AccountStatus" AS ENUM ('CONNECTED', 'DISCONNECTED');

-- CreateTable
CREATE TABLE "LinkedInAccount" (
    "id" TEXT NOT NULL,
    "linkedinId" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "status" "AccountStatus" NOT NULL DEFAULT 'CONNECTED',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LinkedInAccount_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Lead" (
    "id" TEXT NOT NULL,
    "linkedinUrl" TEXT NOT NULL,
    "status" "LeadStatus" NOT NULL DEFAULT 'PENDING',
    "requestSentAt" TIMESTAMP(3),
    "acceptedAt" TIMESTAMP(3),
    "invitationMessage" TEXT,
    "acceptanceMessage" TEXT,
    "followUp1Message" TEXT,
    "followUp1SentAt" TIMESTAMP(3),
    "followUp2Message" TEXT,
    "followUp2SentAt" TIMESTAMP(3),
    "replyMessage" TEXT,
    "linkedinAccountId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Lead_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "LinkedInAccount_linkedinId_key" ON "LinkedInAccount"("linkedinId");

-- CreateIndex
CREATE UNIQUE INDEX "Lead_linkedinUrl_key" ON "Lead"("linkedinUrl");

-- AddForeignKey
ALTER TABLE "Lead" ADD CONSTRAINT "Lead_linkedinAccountId_fkey" FOREIGN KEY ("linkedinAccountId") REFERENCES "LinkedInAccount"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
