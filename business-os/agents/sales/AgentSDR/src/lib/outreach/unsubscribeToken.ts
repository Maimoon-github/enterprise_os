/**
 * Stateless, signed unsubscribe tokens — no DB column needed. Two formats
 * exist, because links already sitting in sent emails must keep working:
 *
 *  - v2 (issued now): base64url(`v2.<organizationId>.<email>.<hmac>`). The
 *    organization is inside the signed payload, so a click suppresses the
 *    address in exactly the organization that mailed it.
 *  - legacy: base64url(`<email>.<hmac>`), from before organizations. It names
 *    no organization; the caller suppresses the address in every organization
 *    whose outreach leads contain it (`organizationId: null` here).
 *
 * Either way a token can unsubscribe only the one address it was issued for.
 */
import { createHmac, timingSafeEqual } from "crypto";

function secret(): string {
  const s = process.env.UNSUBSCRIBE_SECRET;
  if (!s) throw new Error("UNSUBSCRIBE_SECRET is not configured");
  return s;
}

function sign(payload: string): string {
  return createHmac("sha256", secret()).update(payload).digest("hex").slice(0, 32);
}

const signLegacy = (email: string) => sign(email.trim().toLowerCase());
const signV2 = (organizationId: string, email: string) => sign(`v2:${organizationId}:${email.trim().toLowerCase()}`);

const ORGANIZATION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function signatureMatches(provided: string, expected: string): boolean {
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function buildUnsubscribeToken(email: string, organizationId: string): string {
  if (!ORGANIZATION_ID.test(organizationId)) throw new Error("An unsubscribe token needs an organization id");
  const normalized = email.trim().toLowerCase();
  return Buffer.from(`v2.${organizationId}.${normalized}.${signV2(organizationId, normalized)}`).toString("base64url");
}

/** The pre-organization format. Only tests and migrations of old links should need it. */
export function buildLegacyUnsubscribeToken(email: string): string {
  const normalized = email.trim().toLowerCase();
  return Buffer.from(`${normalized}.${signLegacy(normalized)}`).toString("base64url");
}

export type UnsubscribeTokenResult =
  | { ok: true; email: string; /** null for a legacy token: suppress in every organization that mailed the address. */ organizationId: string | null }
  | { ok: false };

export function verifyUnsubscribeToken(token: string): UnsubscribeTokenResult {
  try {
    const decoded = Buffer.from(token, "base64url").toString("utf-8");
    const dot = decoded.lastIndexOf(".");
    if (dot === -1) return { ok: false };
    const rest = decoded.slice(0, dot);
    const providedSig = decoded.slice(dot + 1);

    // v2: "v2.<uuid>.<email>"
    if (rest.startsWith("v2.") && rest[39] === ".") {
      const organizationId = rest.slice(3, 39);
      const email = rest.slice(40);
      if (ORGANIZATION_ID.test(organizationId) && email && signatureMatches(providedSig, signV2(organizationId, email))) {
        return { ok: true, email, organizationId: organizationId.toLowerCase() };
      }
    }

    // legacy: "<email>"
    if (signatureMatches(providedSig, signLegacy(rest))) return { ok: true, email: rest, organizationId: null };
    return { ok: false };
  } catch {
    return { ok: false };
  }
}
