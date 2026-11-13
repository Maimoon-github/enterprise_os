/**
 * Validation for the first-run setup form. Client-safe: the form and the
 * route share it, so the same rules apply before and after the request.
 */

import { isTimeZone } from "@/lib/channels/rules";
import { resolveTimeZone } from "@/lib/timeZone";

export const MIN_PASSWORD_LENGTH = 8; // keep equal to emailAndPassword.minPasswordLength in server.ts
const MAX_PASSWORD_LENGTH = 128; // Better Auth's own default maximum

export type SetupInput = {
  name: string;
  organizationName: string;
  email: string;
  password: string;
  /**
   * The browser's time zone (Intl), sent invisibly with the form: becomes the
   * organization's time zone. Absent when missing or not a zone this runtime
   * knows — never a reason to refuse the form.
   */
  timeZone?: string;
};

export type SetupValidation = { ok: true; value: SetupInput } | { ok: false; error: string };

export function validateSetupInput(raw: unknown): SetupValidation {
  const body = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const str = (key: string) => (typeof body[key] === "string" ? (body[key] as string) : "");

  const name = str("name").trim();
  const organizationName = str("organizationName").trim();
  const email = str("email").trim().toLowerCase();
  const password = str("password"); // never trimmed: spaces may be intended

  if (!name) return { ok: false, error: "Enter your name." };
  if (name.length > 100) return { ok: false, error: "Your name is too long." };
  if (!organizationName) return { ok: false, error: "Enter a name for your organization." };
  if (organizationName.length > 100) return { ok: false, error: "The organization name is too long." };
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { ok: false, error: "Enter a valid email address." };
  if (password.length < MIN_PASSWORD_LENGTH) return { ok: false, error: `Password must be at least ${MIN_PASSWORD_LENGTH} characters.` };
  if (password.length > MAX_PASSWORD_LENGTH) return { ok: false, error: `Password must be at most ${MAX_PASSWORD_LENGTH} characters.` };
  const zone = str("timeZone").trim();
  const timeZone = zone && zone.length <= 64 && isTimeZone(zone) ? resolveTimeZone(zone) : undefined;
  return { ok: true, value: { name, organizationName, email, password, ...(timeZone ? { timeZone } : {}) } };
}
