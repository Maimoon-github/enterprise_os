/**
 * The Call Recorder build this deployment serves. The zip at
 * RECORDER_DOWNLOAD_PATH is built from the same source in `bun run build`,
 * so its version is always this one. Client-safe.
 */

import manifest from "../../../extensions/whatsapp-recorder/static/manifest.json";

export const LATEST_RECORDER_VERSION: string = manifest.version;

export const RECORDER_DOWNLOAD_PATH = "/downloads/call-recorder";

/** The first extension version with its own Update page (the `recorder:update` bridge request). */
export const RECORDER_SELF_UPDATE_VERSION = "0.14.0";

/** Where the download and the install / update steps are shown. */
export const RECORDER_SETUP_PATH = "/settings/whatsapp-connection";

/** True when dotted version `a` is older than `b` ("0.9.0" < "0.13.1"). */
export function isOlderVersion(a: string, b: string): boolean {
  const parse = (value: string) => value.split(".").map((part) => Number.parseInt(part, 10) || 0);
  const left = parse(a);
  const right = parse(b);
  for (let i = 0; i < Math.max(left.length, right.length); i++) {
    const diff = (left[i] ?? 0) - (right[i] ?? 0);
    if (diff !== 0) return diff < 0;
  }
  return false;
}
