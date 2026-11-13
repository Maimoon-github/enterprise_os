-- CreateEnum
CREATE TYPE "SearchQueryStatus" AS ENUM ('QUEUED', 'RUNNING', 'PAUSED_LIMIT', 'COMPLETED', 'FAILED', 'CANCELLED');

-- CreateTable
CREATE TABLE "SearchQuery" (
    "id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "status" "SearchQueryStatus" NOT NULL DEFAULT 'QUEUED',
    "cursor" TEXT,
    "totalCount" INTEGER,
    "leadsFetched" INTEGER NOT NULL DEFAULT 0,
    "lastError" TEXT,
    "currentAccountId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "SearchQuery_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SearchResult" (
    "id" TEXT NOT NULL,
    "searchQueryId" TEXT NOT NULL,
    "linkedinUrl" TEXT NOT NULL,
    "name" TEXT,
    "headline" TEXT,
    "location" TEXT,
    "profilePictureUrl" TEXT,
    "networkDistance" TEXT,
    "followersCount" INTEGER,
    "sharedConnectionsCount" INTEGER,
    "raw" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SearchResult_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "SearchResult_searchQueryId_linkedinUrl_key" ON "SearchResult"("searchQueryId", "linkedinUrl");

-- AddForeignKey
ALTER TABLE "SearchQuery" ADD CONSTRAINT "SearchQuery_currentAccountId_fkey" FOREIGN KEY ("currentAccountId") REFERENCES "LinkedInAccount"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SearchResult" ADD CONSTRAINT "SearchResult_searchQueryId_fkey" FOREIGN KEY ("searchQueryId") REFERENCES "SearchQuery"("id") ON DELETE CASCADE ON UPDATE CASCADE;
