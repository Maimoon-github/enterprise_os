import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { DOCS_PAGES, docsPageUrl, SUPPORT_LINKS } from "./support";

const DOCS = join(import.meta.dir, "../../docs");

/** Mintlify's heading anchor: lower case, punctuation dropped, spaces to hyphens. */
function slug(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

describe("DOCS_PAGES", () => {
  const navigation = readFileSync(join(DOCS, "docs.json"), "utf8");

  for (const entry of DOCS_PAGES) {
    test(`${entry} is a published docs page`, () => {
      const [page, anchor] = entry.split("#");
      const file = join(DOCS, `${page}.mdx`);
      expect(existsSync(file)).toBe(true);
      // Only pages in docs.json's navigation are served.
      expect(navigation).toContain(`"${page}"`);
      if (anchor) {
        const headings = [...readFileSync(file, "utf8").matchAll(/^#{2,4}\s+(.+?)\s*$/gm)].map((match) => slug(match[1]));
        expect(headings).toContain(anchor);
      }
    });
  }

  test("docsPageUrl joins the docs site and the page", () => {
    expect(docsPageUrl("email/connect#add-a-mailbox")).toBe(`${SUPPORT_LINKS.docs}/email/connect#add-a-mailbox`);
  });
});
