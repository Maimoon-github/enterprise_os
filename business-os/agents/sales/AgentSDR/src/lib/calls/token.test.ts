import { describe, expect, test } from "bun:test";
import { createRecorderToken, hashRecorderToken, recorderTokenMatches } from "./token";

describe("createRecorderToken", () => {
  test("returns a token whose hash matches the returned hash", () => {
    const { token, hash } = createRecorderToken();
    expect(hashRecorderToken(token)).toBe(hash);
  });

  test("returns a url-safe, reasonably long random token each time", () => {
    const first = createRecorderToken();
    const second = createRecorderToken();
    expect(first.token).not.toBe(second.token);
    expect(first.token.length).toBeGreaterThanOrEqual(32);
    expect(/^[A-Za-z0-9_-]+$/.test(first.token)).toBe(true);
  });
});

describe("recorderTokenMatches", () => {
  test("accepts the token that produced the hash", () => {
    const { token, hash } = createRecorderToken();
    expect(recorderTokenMatches(token, hash)).toBe(true);
  });

  test("rejects a different token", () => {
    const { hash } = createRecorderToken();
    const { token: otherToken } = createRecorderToken();
    expect(recorderTokenMatches(otherToken, hash)).toBe(false);
  });

  test("rejects a tampered hash of the same length", () => {
    const { token, hash } = createRecorderToken();
    const tampered = hash.slice(0, -1) + (hash.at(-1) === "0" ? "1" : "0");
    expect(recorderTokenMatches(token, tampered)).toBe(false);
  });
});
