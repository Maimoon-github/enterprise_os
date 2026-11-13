/**
 * Prepare the public repository: the committed tree at HEAD, as a brand-new
 * repository with a single commit and no history.
 *
 *   bun run release:prepare -- --out ../agentsdr-public --repo owner/name [--exclude path ...] [--message "AgentSDR 0.1.0"]
 *
 * Why a fresh history: the private history holds things that must never be
 * published (an old credential, early fixtures with real contacts, and the
 * `refs/conductor-checkpoints/*` snapshots). Exporting the tree and
 * committing it once publishes the code as it is today and nothing else.
 *
 * What it does, in order — and it never pushes:
 *   1. Refuses unless the working tree is clean (only committed files ship).
 *   2. Exports HEAD with `git archive` into --out, which must not exist yet.
 *   3. Removes every --exclude path (and the defaults in EXCLUDE below), and
 *      with --repo points every link at the public repository (README,
 *      docs, issue templates, package.json).
 *   4. Refuses if a sensitive-looking file is present (.env files other than
 *      .env.example, dumps, keys, backups).
 *   5. Runs gitleaks over the tree when it is installed (with the repository's
 *      reviewed .gitleaksignore), and refuses on any finding.
 *   6. `git init -b main`, one commit, and prints the push commands.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";

/** Paths never published, whatever --exclude says. Keep this list short and explained. */
const EXCLUDE: string[] = [];

/** Files that must never reach a public repository. */
const SENSITIVE = [
  /(^|\/)\.env(\.|$)(?!example$)/,
  /\.(dump|sql\.gz|pem|p12|pfx|key)$/i,
  /(^|\/)id_(rsa|ed25519)/,
  /(^|\/)agentsdr-backups(\/|$)/,
  /service-account.*\.json$/i,
];

/** The private repository's address, as it appears in links and setup steps. */
const PRIVATE_REPO = "Kandid-ai/AgentSDR";

function args(): { out: string; excludes: string[]; message: string; repo: string | null } {
  const argv = process.argv.slice(2);
  let out = "";
  let repo: string | null = null;
  let message = "AgentSDR";
  const excludes: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (!value || !["--out", "--exclude", "--message", "--repo"].includes(flag)) {
      throw new Error(`Unknown or incomplete argument: ${flag}`);
    }
    if (flag === "--out") out = value;
    if (flag === "--exclude") excludes.push(value);
    if (flag === "--message") message = value;
    if (flag === "--repo") {
      if (!/^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/.test(value)) throw new Error(`--repo must look like owner/name, got ${value}`);
      repo = value;
    }
    i++;
  }
  if (!out) throw new Error("Pass --out <directory> (it must not exist yet)");
  return { out: resolve(out), excludes: [...EXCLUDE, ...excludes], message, repo };
}

function run(cmd: string, cmdArgs: string[], cwd: string): string {
  return execFileSync(cmd, cmdArgs, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

function listFiles(root: string, dir = root): string[] {
  const files: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) files.push(...listFiles(root, path));
    else files.push(relative(root, path));
  }
  return files;
}

function main() {
  const root = run("git", ["rev-parse", "--show-toplevel"], process.cwd()).trim();
  const { out, excludes, message, repo } = args();

  if (run("git", ["status", "--porcelain"], root).trim()) {
    throw new Error("The working tree has uncommitted changes. Commit or stash them: only committed files are published.");
  }
  if (existsSync(out)) throw new Error(`${out} already exists. Choose a new directory.`);
  if (out.startsWith(root + "/")) throw new Error("--out must be outside this repository.");

  const head = run("git", ["rev-parse", "--short", "HEAD"], root).trim();
  console.log(`Exporting ${head} to ${out}`);
  execFileSync("mkdir", ["-p", out]);
  execFileSync("sh", ["-c", `git archive HEAD | tar -x -C "${out}"`], { cwd: root });

  for (const path of excludes) {
    const target = join(out, path);
    if (!target.startsWith(out + "/")) throw new Error(`Refusing to exclude a path outside the tree: ${path}`);
    if (existsSync(target)) {
      rmSync(target, { recursive: true, force: true });
      console.log(`  excluded ${path}`);
    } else {
      console.log(`  (not present: ${path})`);
    }
  }

  if (repo) {
    const [owner, name] = repo.split("/");
    const replacements: [RegExp, string][] = [
      [new RegExp(PRIVATE_REPO.replace("/", "\\/"), "g"), repo],
      [/\bcd AgentSDR_v2\b/g, `cd ${name}`],
      [/ghcr\.io\/kandid-ai\/agentsdr\b/g, `ghcr.io/${owner.toLowerCase()}/agentsdr`],
    ];
    let changed = 0;
    for (const file of listFiles(out)) {
      const path = join(out, file);
      const buffer = readFileSync(path);
      if (buffer.includes(0)) continue; // binary
      const before = buffer.toString("utf8");
      const after = replacements.reduce((text, [pattern, value]) => text.replace(pattern, value), before);
      if (after !== before) {
        writeFileSync(path, after);
        changed++;
      }
    }
    console.log(`  links now point at ${repo} (${changed} files)`);
  }

  const files = listFiles(out);
  const sensitive = files.filter((file) => SENSITIVE.some((pattern) => pattern.test(file)));
  if (sensitive.length) {
    throw new Error(`Sensitive-looking files in the tree, nothing was committed:\n  ${sensitive.join("\n  ")}`);
  }
  console.log(`  ${files.length} files, none sensitive-looking`);

  let scanned = false;
  try {
    run("gitleaks", ["version"], out);
    scanned = true;
  } catch {
    console.warn("  gitleaks is not installed: the secret scan was SKIPPED (brew install gitleaks).");
  }
  if (scanned) {
    try {
      run("gitleaks", ["dir", ".", "--no-banner", "--redact"], out);
      console.log("  gitleaks: no secrets found");
    } catch (error) {
      const detail = error instanceof Error && "stdout" in error ? String((error as { stdout: unknown }).stdout) : "";
      throw new Error(`gitleaks found possible secrets, nothing was committed. Review them, then fix or add to .gitleaksignore:\n${detail}`);
    }
  }

  run("git", ["init", "-q", "-b", "main"], out);
  run("git", ["add", "-A"], out);
  run("git", ["commit", "-q", "-m", message], out);
  const commit = run("git", ["log", "--oneline", "-1"], out).trim();

  console.log(`\nReady: ${out}`);
  console.log(`  one commit: ${commit}`);
  console.log(`  from private ${head}${excludes.length ? `, without ${excludes.join(", ")}` : ""}`);
  console.log("\nTo publish (only when you mean to):");
  console.log(`  cd ${out}`);
  console.log(`  git remote add origin git@github.com:${repo ?? "<owner>/<repo>"}.git`);
  console.log("  git push -u origin main");
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}
