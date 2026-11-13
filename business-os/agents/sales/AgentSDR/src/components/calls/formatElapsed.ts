/**
 * m:ss formatting for calls, shared by the live strip, the calls card and the
 * contact panel. Split out of the components so it can be unit tested without
 * pulling in their tree of imports (CrmLayout → next/link, which needs a full
 * Next.js client React runtime the test environment doesn't provide).
 */

function clock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** A running call's elapsed time. Rounds down, as a ticking clock does. */
export function formatElapsed(ms: number): string {
  return clock(Math.max(0, Math.floor(ms / 1000)));
}

/** A finished call's length, rounded to the nearest second; null when unknown. */
export function formatCallDuration(ms: number | null): string | null {
  return ms == null ? null : clock(Math.max(0, Math.round(ms / 1000)));
}

/** Where in the recording something was said, from seconds (a transcript line). */
export function formatOffset(seconds: number): string {
  return clock(Math.max(0, Math.round(seconds)));
}
