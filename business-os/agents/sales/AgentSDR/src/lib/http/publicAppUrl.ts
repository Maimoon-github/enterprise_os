/**
 * The app's public origin (no trailing slash), read at RUNTIME.
 *
 * `NEXT_PUBLIC_*` variables are inlined into the build, so a Docker image
 * built once would carry whatever value its build had. Server code that
 * builds absolute links — unsubscribe links in emails, Unipile hosted-auth
 * redirects — reads `BETTER_AUTH_URL` instead, which every deployment sets
 * to its public origin and which is read when the server runs. The legacy
 * `NEXT_PUBLIC_APP_URL` is the fallback for deployments that only set it.
 */
export function publicAppUrl(): string | null {
  const value = process.env.BETTER_AUTH_URL || process.env.NEXT_PUBLIC_APP_URL;
  return value ? value.replace(/\/+$/, "") : null;
}
