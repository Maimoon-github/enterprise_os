/**
 * Seed the always-included "sender & contact details" Knowledge document from
 * a Markdown file.
 *
 * Run with:
 *   bun --conditions=react-server scripts/seed-crm-sender-knowledge.ts --file <path> [--title "<title>"] [--apply]
 *
 *   --file   Markdown document to store (template:
 *            scripts/examples/sender-knowledge.example.md). Required.
 *   --title  Document title; defaults to the file's first `# ` heading.
 *   --apply  Write it. Without it the script only reports what it would do.
 *
 * The document is `alwaysInclude`, so it reaches every draft (drafts.ts →
 * retrieveKnowledge) and every classification (handlers.ts classificationContext).
 * Re-running upserts by title and only appends a new version when the content
 * actually changed.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { readFileSync } from "node:fs";
import { runScriptInOrganization } from "./lib/organization";
import {
  createKnowledgeDocument,
  listKnowledgeDocuments,
  updateKnowledgeDocument,
} from "../src/lib/crm/knowledge-service";

function argValue(flag: string): string | undefined {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const file = argValue("--file");
if (!file) {
  console.error('Usage: bun --conditions=react-server scripts/seed-crm-sender-knowledge.ts --file <path> [--title "<title>"] [--apply]');
  process.exit(1);
}

// the service stores trimmed content, so compare like for like
const CONTENT = readFileSync(file, "utf8").trim();
const TITLE = argValue("--title") ?? /^#\s+(.+?)\s*$/m.exec(CONTENT)?.[1];
if (!TITLE) {
  console.error(`No --title given and ${file} has no "# " heading to use as one.`);
  process.exit(1);
}
const KIND = "company";
const TAGS = ["sender", "contact", "scheduling", "policy"];

async function seed(apply: boolean) {
  const existing = (await listKnowledgeDocuments({ includeArchived: true }))
    .find((document) => document.title === TITLE);

  if (!existing) {
    if (!apply) return { action: "create", title: TITLE };
    const created = await createKnowledgeDocument({
      title: TITLE,
      kind: KIND,
      tags: TAGS,
      alwaysInclude: true,
      content: CONTENT,
    });
    return { action: "created", id: created.id, version: created.latestVersion };
  }

  const contentChanged = existing.latest?.content !== CONTENT;
  const metadataChanged = existing.kind !== KIND
    || !existing.alwaysInclude
    || !existing.active
    || JSON.stringify(existing.tags) !== JSON.stringify(TAGS);
  if (!contentChanged && !metadataChanged) return { action: "unchanged", id: existing.id, version: existing.latestVersion };
  if (!apply) return { action: "update", id: existing.id, contentChanged, metadataChanged };
  const updated = await updateKnowledgeDocument(existing.id, {
    kind: KIND,
    tags: TAGS,
    alwaysInclude: true,
    active: true,
    ...(contentChanged ? { content: CONTENT } : {}),
  });
  return { action: "updated", id: updated.id, version: updated.latestVersion, contentChanged, metadataChanged };
}

const apply = process.argv.includes("--apply");
runScriptInOrganization(() => seed(apply))
  .then((summary) => {
    console.log(JSON.stringify({ dryRun: !apply, ...summary }, null, 2));
    process.exit(0);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
