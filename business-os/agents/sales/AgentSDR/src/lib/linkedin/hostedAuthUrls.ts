import { publicAppUrl } from "@/lib/http/publicAppUrl";
/**
 * Absolute URLs Unipile needs for the Hosted Auth wizard.
 *
 * All of them must be absolute and publicly reachable — they are consumed by
 * Unipile's servers and by the browser after it has left our origin, so a
 * relative path is not an option. See https://developer.unipile.com/docs/hosted-auth
 */

/** Where the wizard returns the user; also where the Connect button lives. */
export const HOSTED_AUTH_RETURN_PATH = "/settings/linkedin-accounts";

/** Public, secret-protected endpoint Unipile POSTs the connected account id to. */
export const HOSTED_AUTH_NOTIFY_PATH = "/api/webhooks/unipile-account";

const LOCAL_ORIGIN = /^https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$/;

/**
 * `notifySecret` is the stored Unipile notify secret ("" or omitted: no notify_url).
 * `organizationId` rides along on notify_url so the public endpoint knows whose
 * Unipile workspace is calling before it reads any credentials.
 */
export function hostedAuthCallbackUrls(
  requestOrigin?: string | null,
  notifySecret?: string | null,
  organizationId?: string | null,
): {
  successRedirectUrl: string;
  failureRedirectUrl: string;
  notifyUrl?: string;
} {
  const configured = publicAppUrl();

  // Send the user back to the origin they actually started from. Without this a
  // dev session finishing the wizard lands on production, because
  // the configured origin is the public one. Only a localhost origin may
  // override it, so a forged Origin header cannot turn this into an open redirect.
  const local = requestOrigin && LOCAL_ORIGIN.test(requestOrigin) ? requestOrigin : null;
  const returnOrigin = local ?? configured;
  if (!returnOrigin) {
    throw new Error(
      "BETTER_AUTH_URL is not set — Unipile hosted auth needs absolute redirect URLs"
    );
  }

  // Unipile calls notify_url from their servers, so it cannot point at a
  // developer's machine. Omitted there: the redirect back to the accounts page
  // syncs anyway, which is what makes the flow work locally.
  const notifyOrigin = configured && !LOCAL_ORIGIN.test(configured) ? configured : null;

  return {
    successRedirectUrl: `${returnOrigin}${HOSTED_AUTH_RETURN_PATH}?unipile=success`,
    failureRedirectUrl: `${returnOrigin}${HOSTED_AUTH_RETURN_PATH}?unipile=failure`,
    notifyUrl:
      notifySecret && notifyOrigin
        ? `${notifyOrigin}${HOSTED_AUTH_NOTIFY_PATH}?secret=${encodeURIComponent(notifySecret)}${
            organizationId ? `&org=${encodeURIComponent(organizationId)}` : ""
          }`
        : undefined,
  };
}
