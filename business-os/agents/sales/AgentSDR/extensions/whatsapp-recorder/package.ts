/**
 * Zips the built extension (dist/, from `bun run build:recorder`) into
 * release/agentsdr-call-recorder.zip, which AgentSDR serves to signed-in
 * people at /downloads/call-recorder. Run by `bun run build`, so every deploy
 * serves the extension that matches it.
 *
 * Everything sits under one folder, agentsdr-call-recorder/, so an update
 * unzips to the same folder name the rep loaded unpacked the first time.
 */

import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { zipSync, type Zippable } from "fflate";

const root = import.meta.dir;
const dist = join(root, "dist");
const out = join(root, "release", "agentsdr-call-recorder.zip");
const FOLDER = "agentsdr-call-recorder";

function filesUnder(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? filesUnder(path) : [path];
  });
}

const files = filesUnder(dist);
if (!files.some((path) => relative(dist, path) === "manifest.json")) {
  throw new Error("dist/manifest.json is missing — run `bun run build:recorder` first");
}

const zippable: Zippable = {};
for (const path of files) zippable[`${FOLDER}/${relative(dist, path)}`] = readFileSync(path);

mkdirSync(join(root, "release"), { recursive: true });
writeFileSync(out, zipSync(zippable, { level: 9 }));
console.log(`${relative(process.cwd(), out)}: ${files.length} files`);
