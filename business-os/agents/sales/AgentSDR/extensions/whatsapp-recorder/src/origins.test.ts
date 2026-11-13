import { describe, expect, test } from "bun:test";
import { BUILT_IN_ORIGINS, normalizeOrigin, originPattern } from "./origins";

describe("normalizeOrigin", () => {
  test("adds https:// to a bare host and drops paths", () => {
    expect(normalizeOrigin("sdr.example.com")).toBe("https://sdr.example.com");
    expect(normalizeOrigin("https://sdr.example.com/analytics?x=1")).toBe("https://sdr.example.com");
    expect(normalizeOrigin("  https://SDR.Example.com/  ")).toBe("https://sdr.example.com");
  });
  test("keeps a non-default port", () => {
    expect(normalizeOrigin("https://sdr.example.com:8443")).toBe("https://sdr.example.com:8443");
  });
  test("allows plain http only on localhost", () => {
    expect(normalizeOrigin("http://localhost:3001")).toBe("http://localhost:3001");
    expect(normalizeOrigin("http://127.0.0.1:3000")).toBe("http://127.0.0.1:3000");
    expect(normalizeOrigin("http://sdr.example.com")).toBeNull();
  });
  test("refuses anything that is not a site address", () => {
    for (const bad of ["", "   ", "not a url", "intranet", "ftp://sdr.example.com", "javascript:alert(1)", "https://user:pw@sdr.example.com"]) {
      expect(normalizeOrigin(bad)).toBeNull();
    }
  });
  test("the built-in origins are already normal", () => {
    for (const origin of BUILT_IN_ORIGINS) expect(normalizeOrigin(origin)).toBe(origin);
  });
});

test("originPattern covers every page of the origin", () => {
  expect(originPattern("https://sdr.example.com")).toBe("https://sdr.example.com/*");
});
