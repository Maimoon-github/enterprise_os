export type LegacyRawRecord = {
  raw: Record<string, unknown>;
  sourceRowId: string;
  observedAt: Date | null;
};

export type LegacyRawConflict = {
  key: string;
  value: unknown;
  sourceRowId: string;
  observedAt: string | null;
};

const LEGACY_IDENTITY_KEYS = new Set([
  "email",
  "email_address",
  "work_email",
  "linkedin",
  "linkedinurl",
  "linkedin_url",
  "public_identifier",
  "public_profile_url",
  "profile_url",
  "provider_id",
  "user_provider_id",
]);

/** Keep legacy enrichment fields in raw, but never duplicate canonical identities there. */
export function stripLegacyIdentityFields(raw: Record<string, unknown>): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (LEGACY_IDENTITY_KEYS.has(key.toLowerCase())) continue;
    if (key.toLowerCase() === "contact_info" && value && typeof value === "object" && !Array.isArray(value)) {
      const contact = Object.fromEntries(Object.entries(value as Record<string, unknown>)
        .filter(([contactKey]) => !["email", "emails"].includes(contactKey.toLowerCase())));
      if (Object.keys(contact).length) cleaned[key] = contact;
      continue;
    }
    cleaned[key] = value;
  }
  return cleaned;
}

function stableValue(value: unknown): string {
  if (value === undefined) return "undefined";
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableValue).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, item]) => `${JSON.stringify(key)}:${stableValue(item)}`)
    .join(",")}}`;
}

function hasValue(value: unknown) {
  return value !== null && value !== undefined && value !== "";
}

/**
 * Deterministically merges legacy snapshots for one identity. Newer values win
 * while every older distinct value remains available under
 * `__legacy_conflicts`. Key comparison is case-insensitive because template
 * lookup is case-insensitive.
 */
export function mergeLegacyRawRecords(records: LegacyRawRecord[]): Record<string, unknown> {
  const sorted = [...records].sort((left, right) => {
    const leftTime = left.observedAt?.getTime() ?? 0;
    const rightTime = right.observedAt?.getTime() ?? 0;
    return leftTime - rightTime || left.sourceRowId.localeCompare(right.sourceRowId);
  });
  const winners = new Map<string, { key: string; value: unknown; sourceRowId: string; observedAt: Date | null }>();
  const conflicts: LegacyRawConflict[] = [];

  for (const record of sorted) {
    for (const [key, value] of Object.entries(record.raw)) {
      if (!hasValue(value) || key === "__legacy_conflicts") continue;
      const normalizedKey = key.toLowerCase();
      const previous = winners.get(normalizedKey);
      if (previous && stableValue(previous.value) !== stableValue(value)) {
        conflicts.push({
          key: previous.key,
          value: previous.value,
          sourceRowId: previous.sourceRowId,
          observedAt: previous.observedAt?.toISOString() ?? null,
        });
      }
      winners.set(normalizedKey, { key, value, sourceRowId: record.sourceRowId, observedAt: record.observedAt });
    }
  }

  const merged = Object.fromEntries([...winners.values()].map((winner) => [winner.key, winner.value]));
  if (conflicts.length) merged.__legacy_conflicts = conflicts;
  return merged;
}
