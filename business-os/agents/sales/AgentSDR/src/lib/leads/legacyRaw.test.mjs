import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mergeLegacyRawRecords, stripLegacyIdentityFields } from "./legacyRaw.ts";

describe("mergeLegacyRawRecords", () => {
  it("keeps the newest value and archives the older conflicting value", () => {
    const merged = mergeLegacyRawRecords([
      { raw: { location: "Old City" }, sourceRowId: "old", observedAt: new Date("2025-01-01") },
      { raw: { location: "New City" }, sourceRowId: "new", observedAt: new Date("2026-01-01") },
    ]);
    assert.equal(merged.location, "New City");
    assert.deepEqual(merged.__legacy_conflicts, [{
      key: "location",
      value: "Old City",
      sourceRowId: "old",
      observedAt: "2025-01-01T00:00:00.000Z",
    }]);
  });

  it("treats key casing as the same template variable", () => {
    const merged = mergeLegacyRawRecords([
      { raw: { FirstName: "Pat" }, sourceRowId: "a", observedAt: null },
      { raw: { firstname: "Patricia" }, sourceRowId: "b", observedAt: null },
    ]);
    assert.equal(merged.firstname, "Patricia");
    assert.equal("FirstName" in merged, false);
  });

  it("does not archive identical values or let blanks erase data", () => {
    const merged = mergeLegacyRawRecords([
      { raw: { location: "Delhi" }, sourceRowId: "a", observedAt: null },
      { raw: { location: "Delhi" }, sourceRowId: "b", observedAt: new Date("2026-01-01") },
      { raw: { location: "" }, sourceRowId: "c", observedAt: new Date("2026-02-01") },
    ]);
    assert.equal(merged.location, "Delhi");
    assert.equal("__legacy_conflicts" in merged, false);
  });
});

describe("stripLegacyIdentityFields", () => {
  it("keeps enrichment payload while removing canonical Email and LinkedIn identities", () => {
    assert.deepEqual(stripLegacyIdentityFields({
      email: "person@example.com",
      public_identifier: "person-slug",
      provider_id: "provider-1",
      location: "Delhi",
      contact_info: { emails: ["person@example.com"], phones: ["123"] },
    }), { location: "Delhi", contact_info: { phones: ["123"] } });
  });
});
