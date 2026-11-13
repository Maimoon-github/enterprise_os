/** Stable, mailbox-scoped identity for one Gmail delivery. */
export function gmailInboundEventKey(mailboxAddress: string, gmailMessageId: string) {
  const mailbox = mailboxAddress.trim().toLowerCase();
  const messageId = gmailMessageId.trim();
  if (!mailbox || !messageId) throw new Error("Gmail event identity requires mailbox and message ID");
  return `gmail:${mailbox}:${messageId}`;
}
