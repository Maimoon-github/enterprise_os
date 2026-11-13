import "server-only";

import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

/**
 * Per-call bearer credentials for the recorder extension. The database only
 * ever holds the SHA-256 hash (call_sessions.upload_token_hash) — the raw
 * token exists only in the StartCallResponse and the extension's memory, so
 * a database read alone can never impersonate a recorder.
 */
export function createRecorderToken(): { token: string; hash: string } {
  const token = randomBytes(32).toString("base64url");
  return { token, hash: hashRecorderToken(token) };
}

export function hashRecorderToken(token: string): string {
  return createHash("sha256").update(token, "utf8").digest("hex");
}

/** Constant-time compare so a mistimed response can't leak the hash byte by byte. */
export function recorderTokenMatches(token: string, hash: string): boolean {
  const actual = Buffer.from(hashRecorderToken(token), "hex");
  const expected = Buffer.from(hash, "hex");
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}
