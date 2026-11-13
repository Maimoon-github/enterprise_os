/** The HTTP status carried by an error, or by anything in its cause chain. */
export function errorStatus(error: unknown): number | undefined {
  for (let current: unknown = error; current && typeof current === "object"; current = (current as { cause?: unknown }).cause) {
    const status = (current as { status?: unknown }).status;
    if (typeof status === "number") return status;
  }
  return undefined;
}

const TRANSIENT_MESSAGE =
  /econnrefused|enotfound|eai_again|fetch failed|overloaded|rate.?limit|temporarily/i;

/** The request was sent and we stopped waiting: the provider may still bill it. */
const ABANDONED_MESSAGE = /timed? ?out|timeout|aborted|etimedout|econnreset|socket hang up/i;

/**
 * Whether retrying could help.
 *
 * Only a non-429 4xx (bad request, auth, unknown model) and our own
 * configuration errors — which arrive as plain Errors with no status — are
 * permanent. A 429, any 5xx, a 408 and a connection that never got through
 * are the provider's moment, not the user's config, so the queue should back
 * off and try again.
 *
 * A timeout or a connection dropped mid-request is NOT retried: the model may
 * have generated (and billed) the answer anyway, and a slow model that keeps
 * missing the deadline would otherwise cost three calls per cell.
 */
export function isTransientOpenRouterError(error: unknown): boolean {
  const status = errorStatus(error);
  if (status !== undefined) return status === 429 || status === 408 || status >= 500;
  for (let current: unknown = error; current && typeof current === "object"; current = (current as { cause?: unknown }).cause) {
    const { name, message } = current as { name?: unknown; message?: unknown };
    if (name === "AbortError" || name === "TimeoutError") return false;
    if (typeof message === "string" && ABANDONED_MESSAGE.test(message)) return false;
    if (typeof message === "string" && TRANSIENT_MESSAGE.test(message)) return true;
  }
  return false;
}
