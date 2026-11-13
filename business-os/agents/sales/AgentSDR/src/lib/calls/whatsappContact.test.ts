import { describe, expect, test } from "bun:test";
import { whatsappContactName } from "./whatsappContact";

describe("whatsappContactName", () => {
  const lead = { name: null, detail: null, firstName: null, company: null };
  test("first name, then the company in brackets as the last name", () => {
    expect(whatsappContactName({ ...lead, firstName: " Rahul ", company: "Acme D2C" })).toEqual({
      firstName: "Rahul",
      lastName: "(Acme D2C)",
      display: "Rahul (Acme D2C)",
    });
  });
  test("just the first name when there is no company", () => {
    expect(whatsappContactName({ ...lead, firstName: "Neha", company: " " })).toEqual({
      firstName: "Neha",
      lastName: "",
      display: "Neha",
    });
  });
  test("nothing to save without a first name", () => {
    expect(whatsappContactName({ ...lead, company: "Acme" })).toBeNull();
    expect(whatsappContactName(null)).toBeNull();
  });
});
