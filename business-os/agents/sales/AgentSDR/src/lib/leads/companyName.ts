/**
 * A person's company name. A company row needs a domain, so a company given
 * only by name — typed in a form, or imported without an email to infer a
 * domain from — cannot be linked; records.ts keeps that name in the person's
 * raw instead (company / companyName). This reads both, the linked company
 * first. Pure; safe on the client.
 */
export function personCompanyName(
  raw: Record<string, unknown> | null | undefined,
  linkedName: string | null | undefined,
): string | null {
  const linked = linkedName?.trim();
  if (linked) return linked;
  for (const key of ["companyName", "company"]) {
    const value = raw?.[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}
