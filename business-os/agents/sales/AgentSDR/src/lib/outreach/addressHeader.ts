/** Parses RFC 5322 address headers (From, To, Cc, Reply-To) into normalized addresses. */
import addressparser from "nodemailer/lib/addressparser";
import { dedupeAddresses, isValidEmail, normalizeEmail, type EmailAddress } from "@/lib/email/recipients";

/**
 * Quoted display names with commas and group syntax are handled by
 * nodemailer's parser; invalid addresses are dropped, the rest lowercased
 * and de-duplicated in order.
 */
export function parseAddressHeader(value: string | null | undefined): EmailAddress[] {
  if (!value || !value.trim()) return [];
  const out: EmailAddress[] = [];
  for (const entry of addressparser(value, { flatten: true })) {
    const email = normalizeEmail(entry.address ?? "");
    if (!isValidEmail(email)) continue;
    const name = entry.name?.trim() || null;
    out.push({ email, name: name && name.toLowerCase() !== email ? name : null });
  }
  return dedupeAddresses(out);
}
