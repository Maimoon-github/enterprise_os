import { describe, expect, test } from "bun:test";
import { personCompanyName } from "./companyName";

describe("personCompanyName", () => {
  test("prefers the linked company", () => {
    expect(personCompanyName({ companyName: "Old" }, " Acme ")).toBe("Acme");
  });
  test("falls back to the name kept on the person when no company could be linked", () => {
    expect(personCompanyName({ companyName: "Acme D2C" }, null)).toBe("Acme D2C");
    expect(personCompanyName({ company: "Acme" }, "  ")).toBe("Acme");
  });
  test("null when neither is there", () => {
    expect(personCompanyName({ company: 42 }, null)).toBeNull();
    expect(personCompanyName(null, undefined)).toBeNull();
  });
});
