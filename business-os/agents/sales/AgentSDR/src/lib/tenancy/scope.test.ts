import { describe, expect, test } from "bun:test";
import { currentOrganizationId, maybeCurrentOrganizationId, MissingOrganizationScopeError, runInOrganization } from "./scope";

describe("organization scope", () => {
  test("fails closed outside a scope", () => {
    expect(() => currentOrganizationId()).toThrow(MissingOrganizationScopeError);
    expect(maybeCurrentOrganizationId()).toBeNull();
  });

  test("is visible through awaits inside the scope, and gone after", async () => {
    const seen = await runInOrganization("org-a", async () => {
      await new Promise((resolve) => setTimeout(resolve, 5));
      return currentOrganizationId();
    });
    expect(seen).toBe("org-a");
    expect(maybeCurrentOrganizationId()).toBeNull();
  });

  test("concurrent scopes do not bleed into each other", async () => {
    const run = (org: string, delay: number) =>
      runInOrganization(org, async () => {
        await new Promise((resolve) => setTimeout(resolve, delay));
        return currentOrganizationId();
      });
    expect(await Promise.all([run("org-a", 15), run("org-b", 1), run("org-c", 8)])).toEqual(["org-a", "org-b", "org-c"]);
  });

  test("refuses to switch organization mid-operation", () => {
    expect(() => runInOrganization("org-a", () => runInOrganization("org-b", () => 1))).toThrow(/switch organization/);
    expect(runInOrganization("org-a", () => runInOrganization("org-a", () => currentOrganizationId()))).toBe("org-a");
  });
});
