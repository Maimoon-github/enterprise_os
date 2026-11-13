/**
 * Adds mailboxes from a file and tests each one's Gmail domain-wide delegation
 * via the real connectMailbox() flow — the same code path the "Connect
 * mailbox" UI uses.
 *
 * Bun loads .env.local automatically. Run with:
 *   bun --conditions=react-server scripts/add-mailboxes.ts --file <path> [--signature "<text>"]
 *
 *   --file       one address per line; blank lines and `#` comments allowed
 *                (template: scripts/examples/mailboxes.example.txt)
 *   --signature  optional signature text; `{name}` becomes the capitalised
 *                local part of the address. Default: "Best,\n{name}".
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { readFileSync } from "node:fs";
import { runScriptInOrganization } from "./lib/organization";
import { connectMailbox } from "../src/lib/outreach/mailboxes";

function argValue(flag: string): string | undefined {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const file = argValue("--file");
if (!file) {
  console.error('Usage: bun --conditions=react-server scripts/add-mailboxes.ts --file <path> [--signature "<text>"]');
  process.exit(1);
}
const signatureTemplate = argValue("--signature") ?? "Best,\n{name}";

const TARGETS = readFileSync(file, "utf8")
  .split(/\r?\n/)
  .map((line) => line.replace(/#.*$/, "").trim())
  .filter(Boolean);
if (TARGETS.length === 0) {
  console.error(`No addresses found in ${file}`);
  process.exit(1);
}
const DOMAINS = [...new Set(TARGETS.map((address) => address.split("@")[1]))];

function capitalize(name: string): string {
  return name[0].toUpperCase() + name.slice(1);
}

function signatureFor(name: string): string {
  return signatureTemplate.replaceAll("{name}", capitalize(name));
}

type Result = { emailAddress: string; ok: boolean; error?: string };

async function main() {
  const targets = TARGETS;

  const results: Result[] = [];
  for (const emailAddress of targets) {
    const name = emailAddress.split("@")[0];
    const outcome = await connectMailbox({
      emailAddress,
      displayName: capitalize(name),
      signatureHtml: signatureFor(name),
    });
    results.push(
      outcome.ok
        ? { emailAddress, ok: true }
        : { emailAddress, ok: false, error: outcome.error },
    );
    console.log(`${outcome.ok ? "OK  " : "FAIL"} ${emailAddress}${outcome.ok ? "" : `  — ${outcome.error}`}`);
  }

  const failed = results.filter((r) => !r.ok);
  const byDomain = new Map<string, Result[]>();
  for (const r of results) {
    const domain = r.emailAddress.split("@")[1];
    byDomain.set(domain, [...(byDomain.get(domain) ?? []), r]);
  }

  console.log("\n=== Summary by domain ===");
  for (const domain of DOMAINS) {
    const rows = byDomain.get(domain) ?? [];
    const domainFailed = rows.filter((r) => !r.ok);
    console.log(
      `${domainFailed.length === 0 ? "✔" : "✘"} ${domain}: ${rows.length - domainFailed.length}/${rows.length} connected`,
    );
  }

  console.log(`\nTotal: ${results.length - failed.length}/${results.length} connected`);
  if (failed.length > 0) {
    console.log("\n=== Failures ===");
    for (const f of failed) console.log(`${f.emailAddress}: ${f.error}`);
  }

  process.exit(failed.length > 0 ? 1 : 0);
}

runScriptInOrganization(main).catch((err) => {
  console.error(err);
  process.exit(1);
});
