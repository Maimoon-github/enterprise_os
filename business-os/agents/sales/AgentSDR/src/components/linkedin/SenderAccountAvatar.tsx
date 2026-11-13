"use client";

import { LinkedInAccountTag, type LinkedInAccountRef } from "@/components/linkedin/LinkedInAccountTag";

export type SenderAccount = LinkedInAccountRef;

/** @deprecated Use LinkedInAccountTag */
export function SenderAccountAvatar({
  account,
  size = "sm",
}: {
  account: SenderAccount;
  size?: "sm" | "md";
}) {
  return <LinkedInAccountTag account={account} size={size} />;
}
