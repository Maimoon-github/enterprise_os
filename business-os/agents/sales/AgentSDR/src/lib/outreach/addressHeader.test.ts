import { describe, expect, test } from "bun:test";
import { parseAddressHeader } from "./addressHeader";

describe("parseAddressHeader", () => {
  test("keeps every To address", () => {
    expect(parseAddressHeader("bhagya@skinbae.in, pulkit@getkandid.com").map((a) => a.email)).toEqual([
      "bhagya@skinbae.in",
      "pulkit@getkandid.com",
    ]);
  });

  test("a quoted display name with a comma does not split the address", () => {
    expect(parseAddressHeader('"Doe, Jane" <j@x.com>, b@y.com')).toEqual([
      { email: "j@x.com", name: "Doe, Jane" },
      { email: "b@y.com", name: null },
    ]);
  });

  test("group syntax is flattened", () => {
    expect(parseAddressHeader("Team: a@x.com, b@x.com;").map((a) => a.email)).toEqual(["a@x.com", "b@x.com"]);
  });

  test("lowercases and trims", () => {
    expect(parseAddressHeader("  Jane <JANE@X.COM> ")).toEqual([{ email: "jane@x.com", name: "Jane" }]);
  });

  test("drops garbage and empties", () => {
    expect(parseAddressHeader("not an address, <>, ok@x.com")).toEqual([{ email: "ok@x.com", name: null }]);
    expect(parseAddressHeader(null)).toEqual([]);
    expect(parseAddressHeader("")).toEqual([]);
  });

  test("dedupes case-insensitively, first wins", () => {
    expect(parseAddressHeader("A <a@x.com>, a@X.com").map((a) => a.email)).toEqual(["a@x.com"]);
  });
});
