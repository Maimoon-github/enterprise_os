import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import * as tar from "tar";
import type { WorkerStation } from "../../../src/lib/calls/stationContract";
import { commitProfile, profileUploadUrl } from "./api";
import { log } from "./log";

/**
 * A calling number's CloakBrowser profile lives in AgentSDR (R2, behind the
 * API), not on this worker's disk: before a job the worker restores the
 * saved version into a local folder, and after it packs the folder and
 * saves it as the next version. The local folder is only a cache — when its
 * version marker matches the saved version, the download is skipped.
 *
 * The fingerprint comes from the database too: CloakBrowser reads a
 * profile's seed from `.cloakbrowser-seed`, and the worker writes the
 * number's seed there before every launch, so the number keeps one device
 * identity even if this disk is lost.
 */

const VERSION_MARKER = ".agentsdr-profile-version";
const SEED_FILE = ".cloakbrowser-seed";
/**
 * What is not worth saving: caches the browser rebuilds, crash and metrics
 * data, and the lock files of a running browser. WhatsApp Web's login lives
 * in IndexedDB, Local Storage and cookies, which are kept.
 */
const SKIP = /(^|\/)(Service Worker|Cache|Code Cache|GPUCache|DawnGraphiteCache|DawnWebGPUCache|GrShaderCache|GraphiteDawnCache|ShaderCache|CacheStorage|component_crx_cache|Crashpad|BrowserMetrics|Safe Browsing|optimization_guide_model_store|OptimizationHints|segmentation_platform|Singleton[A-Za-z]*)(\/|$)/;

export async function restoreProfile(station: WorkerStation, dir: string): Promise<void> {
  const tag = `profile @ ${station.name}`;
  await mkdir(dir, { recursive: true });
  const local = Number((await readFile(join(dir, VERSION_MARKER), "utf8").catch(() => "0")).trim()) || 0;
  if (station.profile.version > 0 && station.profile.downloadUrl && local !== station.profile.version) {
    const started = Date.now();
    const response = await fetch(station.profile.downloadUrl);
    if (!response.ok || !response.body) throw new Error(`could not download the saved profile (HTTP ${response.status})`);
    const archive = join(tmpdir(), `agentsdr-profile-${station.id}-${Date.now()}.tar.gz`);
    try {
      await pipeline(Readable.fromWeb(response.body as never), createWriteStream(archive));
      // A fresh folder: leftovers of an older version must not mix with the saved one.
      await rm(dir, { recursive: true, force: true });
      await mkdir(dir, { recursive: true });
      await tar.x({ file: archive, cwd: dir });
      await writeFile(join(dir, VERSION_MARKER), String(station.profile.version));
      log(`${tag}: restored v${station.profile.version} (${mb((await stat(archive)).size)}) in ${Date.now() - started} ms`);
    } finally {
      await rm(archive, { force: true });
    }
  } else if (station.profile.version > 0) {
    log(`${tag}: local copy is v${local}, current`);
  }
  await writeFile(join(dir, SEED_FILE), `${station.fingerprintSeed}\n`);
}

/**
 * Starts the number over logged out: its session is the wrong WhatsApp
 * account. The local copy goes; the fingerprint seed is written back, so
 * the number keeps its device identity. The next save replaces the saved
 * version with the newly linked session.
 */
export async function resetProfile(station: WorkerStation, dir: string): Promise<void> {
  await rm(dir, { recursive: true, force: true });
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, SEED_FILE), `${station.fingerprintSeed}\n`);
  log(`profile @ ${station.name}: discarded the logged-in session for a fresh link`);
}

/**
 * Drops the profile's service-worker registrations and their script cache
 * before a launch. Chrome caches the extension's background script there and,
 * for an extension loaded from a folder at launch, never refreshes it: a
 * number's calls kept running the background script from the day its profile
 * was made (extension 0.17.3) beside current page scripts — no station flag,
 * so the agent played on the speakers; no call log (23 Oct 2026). WhatsApp
 * Web's login is in IndexedDB and Local Storage, and its own service worker
 * registers again on load.
 */
export async function purgeServiceWorkers(dir: string): Promise<void> {
  await rm(join(dir, "Default", "Service Worker"), { recursive: true, force: true });
}

/** Packs the closed browser's profile and saves it as the number's next version. Never throws. */
export async function saveProfile(station: WorkerStation, dir: string): Promise<void> {
  const tag = `profile @ ${station.name}`;
  const archive = join(tmpdir(), `agentsdr-profile-${station.id}-${Date.now()}.tar.gz`);
  try {
    const started = Date.now();
    await tar.c({ gzip: true, file: archive, cwd: dir, portable: true, filter: (path) => !SKIP.test(path.replace(/^\.\//, "")) }, ["."]);
    const bytes = (await stat(archive)).size;
    const { url, headers, key } = await profileUploadUrl(station.id, bytes);
    const put = await fetch(url, {
      method: "PUT",
      headers: { ...headers, "Content-Length": String(bytes) },
      body: Readable.toWeb(createReadStream(archive)) as never,
      duplex: "half",
    } as RequestInit);
    if (!put.ok) throw new Error(`storage answered ${put.status}`);
    const { version } = await commitProfile(station.id, { key, bytes, baseVersion: station.profile.version });
    await writeFile(join(dir, VERSION_MARKER), String(version));
    log(`${tag}: saved v${version} (${mb(bytes)}) in ${Date.now() - started} ms`);
  } catch (error) {
    log(`${tag}: not saved — ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    await rm(archive, { force: true });
  }
}

function mb(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
