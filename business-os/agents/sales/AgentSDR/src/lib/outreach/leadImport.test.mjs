import { describe, expect, test } from "bun:test";
import * as XLSX from "xlsx";
import {
  parseRows,
  parseRowsWithMapping,
  planEmailCampaignImport,
  spreadsheetPreview,
  suggestedEmailMapping,
} from "./leadImport.ts";

function workbookBuffer(rows) {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(rows), "Leads");
  return XLSX.write(workbook, { type: "array", bookType: "xlsx" });
}

describe("Email campaign lead mapping", () => {
  test("maps canonical identity fields and preserves unknown merge fields", () => {
    const result = parseRows(workbookBuffer([{
      Email: "Person@Example.com",
      "LinkedIn URL": "https://linkedin.com/in/person",
      "First Name": "Pat",
      "Last Name": "Lee",
      Company: "Acme",
      "Company Domain": "acme.com",
      "Job Title": "VP Sales",
      Region: "APAC",
    }]));
    expect(result.error).toBeNull();
    expect(result.rows[0]).toMatchObject({
      email: "person@example.com",
      linkedinUrl: "https://linkedin.com/in/person",
      firstName: "Pat",
      lastName: "Lee",
      company: "Acme",
      domain: "acme.com",
      title: "VP Sales",
      customFields: { region: "APAC" },
    });
  });

  test("maps capitalization and underscore variants to canonical columns", () => {
    const result = parseRows(workbookBuffer([{
      EMAIL: "person@example.com",
      First_Name: "Pat",
      LAST_NAME: "Lee",
      JOB_TITLE: "VP Sales",
      COMPANY_DOMAIN: "acme.com",
      Favorite_Color: "Blue",
    }]));
    expect(result.rows[0]).toMatchObject({
      firstName: "Pat",
      lastName: "Lee",
      title: "VP Sales",
      domain: "acme.com",
      customFields: { favorite_color: "Blue" },
    });
  });

  test("keeps populated rows with missing email so the importer can report them", () => {
    const result = parseRows(workbookBuffer([{ Email: "", "First Name": "Pat" }]));
    expect(result.error).toBeNull();
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].email).toBe("");
  });

  test("turns punctuation-heavy headers into usable template tokens", () => {
    const result = parseRows(workbookBuffer([{ Email: "person@example.com", "Intent score (%)": "91" }]));
    expect(result.rows[0].customFields).toEqual({ intentScore: "91" });
  });

  test("previews and imports user-selected columns instead of guessing", () => {
    const buffer = workbookBuffer([{ "Primary inbox": "person@example.com", Given: "Pat", Segment: "Enterprise" }]);
    const preview = spreadsheetPreview(buffer);
    expect(preview.headers).toEqual(["Primary inbox", "Given", "Segment"]);
    expect(suggestedEmailMapping(preview.headers).email).toBeUndefined();
    const result = parseRowsWithMapping(buffer, { email: "Primary inbox", firstName: "Given" });
    expect(result.rows[0]).toMatchObject({ email: "person@example.com", firstName: "Pat", customFields: { segment: "Enterprise" } });
  });

  test("suggests common export column aliases", () => {
    expect(suggestedEmailMapping([
      "Work Email",
      "LinkedIn Profile",
      "Given Name",
      "Family Name",
      "Organisation",
      "Website",
      "Company LinkedIn",
      "Role",
    ])).toEqual({
      email: "Work Email",
      linkedinUrl: "LinkedIn Profile",
      firstName: "Given Name",
      lastName: "Family Name",
      companyName: "Organisation",
      companyDomain: "Website",
      companyLinkedinUrl: "Company LinkedIn",
      title: "Role",
    });
  });

  test("rejects assigning one source column to two canonical fields", () => {
    const buffer = workbookBuffer([{ Identity: "person@example.com" }]);
    expect(parseRowsWithMapping(buffer, { email: "Identity", firstName: "Identity" }).error).toContain("only one");
  });
});

describe("Email campaign identity reuse", () => {
  const row = (email, customFields = {}) => ({
    email,
    linkedinUrl: null,
    firstName: null,
    lastName: null,
    company: null,
    domain: null,
    title: null,
    customFields,
  });

  test("refreshes an existing campaign Person without enrolling a second lead", () => {
    const result = planEmailCampaignImport(
      [row("person@example.com", { newSignal: "yes" })],
      new Set(),
      new Set(["person@example.com"]),
    );
    expect(result.workItems).toEqual([{ row: row("person@example.com", { newSignal: "yes" }), enroll: false }]);
    expect(result.imported).toBe(0);
    expect(result.skippedDuplicate).toBe(1);
  });

  test("updates all valid duplicate rows but enrolls their email only once", () => {
    const result = planEmailCampaignImport(
      [row("person@example.com", { firstSignal: "yes" }), row("person@example.com", { secondSignal: "yes" })],
      new Set(),
      new Set(),
    );
    expect(result.workItems.map((item) => item.enroll)).toEqual([true, false]);
    expect(result.imported).toBe(1);
    expect(result.skippedDuplicate).toBe(1);
  });

  test("does not update People for suppressed or invalid rows", () => {
    const result = planEmailCampaignImport(
      [row("blocked@example.com"), row("not-an-email")],
      new Set(["blocked@example.com"]),
      new Set(),
    );
    expect(result.workItems).toHaveLength(0);
    expect(result.skippedSuppressed).toBe(1);
    expect(result.failed).toHaveLength(1);
  });
});
