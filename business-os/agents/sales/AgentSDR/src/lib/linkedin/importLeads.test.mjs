import { describe, expect, test } from "bun:test";
import { PgDialect } from "drizzle-orm/pg-core";
import {
  IMPORT_FAILURE,
  IMPORT_BATCH_SIZE,
  advisoryLockStatement,
  chunkArray,
  importLeadRows,
  mapSpreadsheetRows,
  mapSpreadsheetRowsWithMapping,
  personRaw,
  suggestedLinkedinMapping,
} from "./importLeads.ts";

describe("LinkedIn campaign lead mapping", () => {
  test("keeps cross-channel identity and company fields for the canonical person", () => {
    const [row] = mapSpreadsheetRows([{
      "LinkedIn URL": "https://linkedin.com/in/person",
      Email: "person@example.com",
      Name: "Pat Lee",
      "Job Title": "VP Sales",
      Company: "Acme",
      "Company Domain": "acme.com",
    }]);
    expect(row).toMatchObject({
      linkedinUrl: "https://linkedin.com/in/person",
      email: "person@example.com",
      name: "Pat Lee",
      headline: "VP Sales",
      companyName: "Acme",
      companyDomain: "acme.com",
    });
  });

  test("stores only unmapped fields in raw", () => {
    const input = {
      "LinkedIn URL": "https://linkedin.com/in/person",
      Email: "person@example.com",
      Name: "Pat Lee",
      "Job Title": "VP Sales",
      Region: "APAC",
    };
    const [mapped] = mapSpreadsheetRows([input]);
    expect(personRaw(mapped, input)).toEqual({ Region: "APAC" });
    expect(personRaw(mapped, input)).not.toHaveProperty("Email");
    expect(personRaw(mapped, input)).not.toHaveProperty("LinkedIn URL");
  });

  test("preserves mapped profile fields that do not have typed People columns", () => {
    const input = {
      "LinkedIn URL": "https://linkedin.com/in/person",
      Location: "Singapore",
      "Profile Picture URL": "https://example.com/person.jpg",
    };
    const [mapped] = mapSpreadsheetRows([input]);
    // The picture has a typed column on people now, so it no longer rides in raw.
    expect(mapped.profilePictureUrl).toBe("https://example.com/person.jpg");
    expect(personRaw(mapped, input)).toEqual({ location: "Singapore" });
  });

  test("adds template-safe aliases for unmapped spreadsheet headers", () => {
    const input = { "LinkedIn URL": "https://linkedin.com/in/person", "Intent score (%)": "91" };
    const [mapped] = mapSpreadsheetRows([input]);
    expect(personRaw(mapped, input)).toEqual({ "Intent score (%)": "91", intentScore: "91" });
  });

  test("uses explicit LinkedIn mappings and keeps other columns as raw variables", () => {
    const [input] = mapSpreadsheetRowsWithMapping(
      [{ Profile: "https://linkedin.com/in/person", Person: "Pat Lee", Segment: "Enterprise" }],
      { linkedinUrl: "Profile", name: "Person" },
    );
    expect(input.mapped).toMatchObject({ linkedinUrl: "https://linkedin.com/in/person", name: "Pat Lee" });
    expect(personRaw(input.mapped, input.raw, input.mappedHeaders)).toEqual({ Segment: "Enterprise" });
  });

  test("keeps recognized but deliberately unmapped columns as raw variables", () => {
    const raw = {
      Profile: "https://linkedin.com/in/person",
      "First Name": "Pat",
      Email: "person@example.com",
    };
    const [input] = mapSpreadsheetRowsWithMapping([raw], {
      linkedinUrl: "Profile",
    });

    expect(personRaw(input.mapped, input.raw, input.mappedHeaders)).toEqual({
      "First Name": "Pat",
      firstName: "Pat",
      Email: "person@example.com",
    });
  });

  test("maps separate first and last names into typed People fields", () => {
    const raw = {
      Profile: "https://linkedin.com/in/person",
      "Given Name": "Pat",
      "Family Name": "Lee",
      Segment: "Enterprise",
    };
    const [input] = mapSpreadsheetRowsWithMapping(
      [raw],
      { linkedinUrl: "Profile", firstName: "Given Name", lastName: "Family Name" },
    );
    expect(input.mapped).toMatchObject({ firstName: "Pat", lastName: "Lee", name: null });
    expect(input.sourceMapping).toEqual({
      linkedinUrl: "Profile",
      firstName: "Given Name",
      lastName: "Family Name",
    });
    expect(personRaw(input.mapped, input.raw, input.mappedHeaders)).toEqual({ Segment: "Enterprise" });
  });

  test("automatically recognizes first-name and last-name aliases as typed fields", () => {
    const raw = {
      "LinkedIn URL": "https://linkedin.com/in/person",
      FirstName: "Pat",
      "Family Name": "Lee",
      Region: "APAC",
    };
    const [mapped] = mapSpreadsheetRows([raw]);
    expect(mapped).toMatchObject({ firstName: "Pat", lastName: "Lee" });
    expect(personRaw(mapped, raw)).toEqual({ Region: "APAC" });
  });

  test("maps the provider API hint used to decode an opaque identifier", () => {
    const [input] = mapSpreadsheetRowsWithMapping(
      [{ Profile: "ACwAAOpaque", API: "sales_navigator" }],
      { linkedinUrl: "Profile", linkedinApi: "API" },
    );
    expect(input.mapped).toMatchObject({ linkedinUrl: "ACwAAOpaque", linkedinApi: "sales_navigator" });
  });

  test("carries the company LinkedIn column through to the company record", () => {
    const [input] = mapSpreadsheetRowsWithMapping(
      [{
        Profile: "https://linkedin.com/in/person",
        Website: "acme.com",
        "Company Linkedin": "http://www.linkedin.com/company/bliss-lifesciences",
      }],
      { linkedinUrl: "Profile", companyDomain: "Website", companyLinkedinUrl: "Company Linkedin" },
    );
    expect(input.mapped.companyLinkedinUrl).toBe("http://www.linkedin.com/company/bliss-lifesciences");
    // Mapped explicitly, so it must not also land in the person's raw blob.
    expect(personRaw(input.mapped, input.raw, input.mappedHeaders)["Company Linkedin"]).toBeUndefined();
  });

  test("suggests common export column aliases", () => {
    expect(suggestedLinkedinMapping([
      "LinkedIn Profile",
      "Work Email",
      "Given Name",
      "Family Name",
      "Organisation",
      "Website",
      "Company LinkedIn",
      "Role",
    ])).toEqual({
      linkedinUrl: "LinkedIn Profile",
      email: "Work Email",
      firstName: "Given Name",
      lastName: "Family Name",
      companyName: "Organisation",
      companyDomain: "Website",
      companyLinkedinUrl: "Company LinkedIn",
      headline: "Role",
    });
  });
});

describe("LinkedIn import validation", () => {
  test("chunks bulk work without dropping order or rows", () => {
    expect(chunkArray([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunkArray([], IMPORT_BATCH_SIZE)).toEqual([]);
  });

  test("rejects invalid bulk batch sizes", () => {
    expect(() => chunkArray([1], 0)).toThrow("positive integer");
    expect(() => chunkArray([1], 1.5)).toThrow("positive integer");
  });

  test("defines explicit failures for invalid cross-channel identity", () => {
    expect(IMPORT_FAILURE.CAMPAIGN_REQUIRED).toContain("destination campaign");
    expect(IMPORT_FAILURE.INVALID_EMAIL).toBe("Invalid email address");
    expect(IMPORT_FAILURE.EMAIL_IDENTITY_CONFLICT).toContain("multiple LinkedIn profiles");
  });

  test("rejects database-only imports before touching persistence", async () => {
    await expect(importLeadRows([], {})).rejects.toThrow(IMPORT_FAILURE.CAMPAIGN_REQUIRED);
  });
});

describe("advisory lock statement", () => {
  const compile = (keys) => new PgDialect().sqlToQuery(advisoryLockStatement(keys));

  test("binds every lock key as a parameter", () => {
    const { sql: text, params } = compile(["company:acme.com", "company:beta.io"]);
    expect(params).toEqual(["company:acme.com", "company:beta.io"]);
    expect(text).toContain("ARRAY[$1, $2]::text[]");
  });

  // A namespace written into the template renders as `company:$1`, which
  // Postgres rejects with `syntax error at or near ":"`. The prefix has to
  // travel inside the parameter value.
  test("never writes a key namespace into the statement", () => {
    const { sql: text } = compile(["company:acme.com", "person:email:a@b.com"]);
    expect(text).not.toContain("company:");
    expect(text).not.toContain("person:email:");
  });

  test("stays valid for an empty batch", () => {
    const { sql: text, params } = compile([]);
    expect(params).toEqual([]);
    expect(text).toContain("ARRAY[]::text[]");
  });
});
