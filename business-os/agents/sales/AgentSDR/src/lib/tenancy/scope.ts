import "server-only";

import { AsyncLocalStorage } from "node:async_hooks";
import { eq, type Column } from "drizzle-orm";

/**
 * The organization the current unit of work acts for.
 *
 * Every entry point opens a scope once — a route handler after
 * requireOrgContext(), a server page after requirePageOrgContext(), a worker
 * or webhook per item after it has resolved the item's organization — and
 * everything it calls reads the organization from here:
 *
 *   return runInOrganization(ctx.organizationId, async () => { … });
 *
 *   db.select().from(people).where(and(inOrg(people), eq(people.id, id)))
 *   db.insert(people).values({ organizationId: currentOrganizationId(), … })
 *
 * Lib functions therefore keep their signatures, and the same function
 * serves a request, a background job and a webhook.
 *
 * It fails closed: currentOrganizationId() outside a scope throws, so a code
 * path nobody scoped errors loudly instead of reading or writing across
 * organizations.
 */

type OrganizationScope = { organizationId: string };

const storage = new AsyncLocalStorage<OrganizationScope>();

export class MissingOrganizationScopeError extends Error {
  constructor() {
    super("No organization scope: this code must run inside runInOrganization()");
    this.name = "MissingOrganizationScopeError";
  }
}

/** Run `fn` (and everything it awaits) as `organizationId`. Nested calls must agree. */
export function runInOrganization<T>(organizationId: string, fn: () => T): T {
  const outer = storage.getStore();
  if (outer && outer.organizationId !== organizationId) {
    throw new Error(`Refusing to switch organization scope mid-operation (${outer.organizationId} → ${organizationId})`);
  }
  return storage.run({ organizationId }, fn);
}

/** The organization in scope; throws MissingOrganizationScopeError if there is none. */
export function currentOrganizationId(): string {
  const scope = storage.getStore();
  if (!scope) throw new MissingOrganizationScopeError();
  return scope.organizationId;
}

/** The organization in scope, or null — for code that legitimately runs both ways. */
export function maybeCurrentOrganizationId(): string | null {
  return storage.getStore()?.organizationId ?? null;
}

/** `table.organizationId = <current organization>` — the filter every scoped read and write carries. */
export function inOrg(table: { organizationId: Column }) {
  return eq(table.organizationId, currentOrganizationId());
}
