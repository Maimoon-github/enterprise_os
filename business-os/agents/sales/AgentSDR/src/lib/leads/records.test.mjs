import { describe, expect, test } from "bun:test";
import { assertCompatiblePersonIdentities, mergePersonRaw, resolvePersonNames } from "./records.ts";

describe("canonical person name mapping", () => {
  test("splits a mapped full name into reusable typed name fields", () => {
    expect(resolvePersonNames({ fullName: "Pat Lee" })).toEqual({
      firstName: "Pat",
      lastName: "Lee",
      fullName: "Pat Lee",
    });
  });

  test("a partial update preserves the other name and rebuilds full name", () => {
    expect(resolvePersonNames(
      { firstName: "Patrick" },
      { firstName: "Pat", lastName: "Lee", fullName: "Pat Lee" },
    )).toEqual({
      firstName: "Patrick",
      lastName: "Lee",
      fullName: "Patrick Lee",
    });
  });

  test("authoritative profile names replace imported placeholder names", () => {
    expect(resolvePersonNames(
      { firstName: "Asha", lastName: "Shah", fullName: "Asha Shah" },
      { firstName: "LinkedIn", lastName: "Member", fullName: "LinkedIn Member" },
      { replaceExisting: true },
    )).toEqual({
      firstName: "Asha",
      lastName: "Shah",
      fullName: "Asha Shah",
    });
  });

  test("authoritative profile names do not retain a missing placeholder surname", () => {
    expect(resolvePersonNames(
      { firstName: "Asha", lastName: null, fullName: "Asha" },
      { firstName: "LinkedIn", lastName: "Member", fullName: "LinkedIn Member" },
      { replaceExisting: true },
    )).toEqual({
      firstName: "Asha",
      lastName: null,
      fullName: "Asha",
    });
  });
});

describe("canonical person identity safety", () => {
  test("allows filling an identity that was previously missing", () => {
    expect(() => assertCompatiblePersonIdentities(
      { email: "pat@example.com", linkedinUrl: null },
      { email: "pat@example.com", linkedinUrl: "pat-lee" },
    )).not.toThrow();
  });

  test("rejects replacing an existing LinkedIn identity through an email match", () => {
    expect(() => assertCompatiblePersonIdentities(
      { email: "pat@example.com", linkedinUrl: "pat-lee" },
      { email: "pat@example.com", linkedinUrl: "someone-else" },
    )).toThrow("different LinkedIn profile");
  });

  test("rejects replacing an existing email identity through a LinkedIn match", () => {
    expect(() => assertCompatiblePersonIdentities(
      { email: "pat@example.com", linkedinUrl: "pat-lee" },
      { email: "other@example.com", linkedinUrl: "pat-lee" },
    )).toThrow("different email address");
  });
});

describe("canonical person enrichment merge", () => {
  test("appends new raw fields and only overwrites keys supplied by the new import", () => {
    expect(mergePersonRaw(
      { region: "APAC", score: "80", originalSource: "search" },
      { score: "91", segment: "Enterprise" },
    )).toEqual({
      region: "APAC",
      score: "91",
      originalSource: "search",
      segment: "Enterprise",
    });
  });

  test("treats a missing existing raw object as empty", () => {
    expect(mergePersonRaw(null, { segment: "Enterprise" })).toEqual({ segment: "Enterprise" });
  });
});
