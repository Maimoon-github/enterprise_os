/** Aggregates every read-only migration audit into one go/no-go result. */
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const stageArg = process.argv.find((value) => value.startsWith("--stage="))?.slice("--stage=".length) ?? "baseline";
if (!["baseline", "ready", "cutover"].includes(stageArg)) {
  throw new Error("--stage must be baseline, ready, or cutover");
}
const readyStage = stageArg === "ready" || stageArg === "cutover";
const cutoverStage = stageArg === "cutover";
const commands: Array<{ name: string; script: string; args: string[] }> = [
  { name: "schema", script: "scripts/check-lead-schema.ts", args: [] },
  { name: "messageDuplicates", script: "scripts/audit-linkedin-message-duplicates.ts", args: [] },
  { name: "rawConflicts", script: "scripts/classify-legacy-raw-conflicts.ts", args: [] },
  { name: "crossChannelIdentity", script: "scripts/audit-cross-channel-identities.ts", args: [] },
  // Pending rows may intentionally retain a source identifier. The deployed
  // resolver fills People.linkedin_url and Lead.providerId before invitation.
  { name: "linkedinIdentifiers", script: "scripts/audit-legacy-linkedin-identifiers.ts", args: [] },
  { name: "providerCollisions", script: "scripts/audit-linkedin-provider-collisions.ts", args: [] },
  ...(readyStage ? [
    { name: "backfillDryRun", script: "scripts/backfill-campaign-people.ts", args: [] },
    ...(cutoverStage ? [{ name: "finalizationCheck", script: "scripts/finalize-lead-tables.ts", args: [] }] : []),
  ] : []),
];

const results = commands.map(({ name, script, args }) => {
  const childEnv = script === "scripts/backfill-campaign-people.ts"
    ? {
        ...process.env,
        PGOPTIONS: `${process.env.PGOPTIONS ?? ""} -c default_transaction_read_only=on`.trim(),
      }
    : process.env;
  const run = spawnSync("bun", ["--conditions=react-server", script, ...args], {
    cwd: process.cwd(),
    env: childEnv,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  process.stdout.write(run.stdout);
  process.stderr.write(run.stderr);
  return {
    name,
    script,
    args,
    exitCode: run.status ?? 1,
    passed: run.status === 0,
    stdout: run.stdout.trim(),
    stderr: run.stderr.trim(),
  };
});

const report = {
  checkedAt: new Date().toISOString(),
  mode: "read-only",
  stage: stageArg,
  passed: results.every((result) => result.passed),
  results,
};
mkdirSync(resolve("reports/migration"), { recursive: true });
const reportPath = resolve("reports/migration/preflight-latest.json");
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
console.log(JSON.stringify(report, null, 2));
if (!report.passed) process.exitCode = 2;
