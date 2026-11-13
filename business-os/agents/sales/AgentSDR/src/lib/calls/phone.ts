import { parsePhoneNumberFromString, type CountryCode } from "libphonenumber-js";
import { digitsOnly } from "./digits";

const COUNTRY_CODE_PATTERN = /^[A-Z]{2}$/;

function asCountryCode(value: string | undefined): CountryCode | undefined {
  return value && COUNTRY_CODE_PATTERN.test(value) ? (value as CountryCode) : undefined;
}

/**
 * Normalizes messy phone input ("+91 98765-43210", "0091 98765 43210",
 * "(415) 555-2671") into E.164 — the only shape people.phone and
 * call_sessions.phone ever store.
 *
 * Input given without a leading "+" only parses against `defaultCountry`:
 * libphonenumber-js has no other way to know which country's dialing rules
 * apply to a bare local number, so ambiguous input with no default
 * configured comes back null rather than a guess.
 *
 * The default is DEFAULT_PHONE_COUNTRY, read at runtime (this runs on the
 * server only). NEXT_PUBLIC_DEFAULT_PHONE_COUNTRY is the older name; a
 * NEXT_PUBLIC_ value is fixed at build time, and the Docker build sees no env.
 */
export function normalizePhone(
  input: string,
  defaultCountry: string | undefined = process.env.DEFAULT_PHONE_COUNTRY ?? process.env.NEXT_PUBLIC_DEFAULT_PHONE_COUNTRY,
): string | null {
  const trimmed = input?.trim();
  if (!trimmed) return null;
  try {
    const parsed = parsePhoneNumberFromString(trimmed, asCountryCode(defaultCountry));
    return parsed?.isValid() ? parsed.number : null;
  } catch {
    return null;
  }
}

/** Digits only, no "+" — what web.whatsapp.com/send?phone= expects. */
export function whatsappDigits(e164: string): string {
  return digitsOnly(e164);
}
