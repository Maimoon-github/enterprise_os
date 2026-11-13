/*
  Warnings:

  - You are about to drop the column `chatId` on the `Lead` table. All the data in the column will be lost.
  - You are about to drop the column `replyMessage` on the `Lead` table. All the data in the column will be lost.
  - You are about to drop the column `chatId` on the `Message` table. All the data in the column will be lost.

*/
-- AlterEnum
ALTER TYPE "MessageType" ADD VALUE 'CUSTOM_SENT';

-- AlterTable
ALTER TABLE "Lead" DROP COLUMN "chatId",
DROP COLUMN "replyMessage";

-- AlterTable
ALTER TABLE "Message" DROP COLUMN "chatId",
ADD COLUMN     "linkedinMessageId" TEXT;
