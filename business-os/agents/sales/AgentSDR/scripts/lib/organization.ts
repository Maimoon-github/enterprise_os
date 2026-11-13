/**
 * Shared by one-shot scripts that call app lib code (which reads the
 * organization from an AsyncLocalStorage scope and throws outside one) or
 * write scoped tables directly.
 *
 * The organization is ORGANIZATION_ID if set, otherwise the initial
 * organization (the original single workspace: metadata {"initial": true}).
 *
 * runScriptInOrganization needs `--conditions=react-server` (tenancy/scope
 * imports `server-only`); resolveScriptOrganization alone does not, for
 * scripts that only run raw SQL and need the id to put in organization_id.
 */
import postgres from "postgres";

export type ScriptOrganization = { id: string; name: string };

export async function resolveScriptOrganization(): Promise<ScriptOrganization> {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  const sql = postgres(url, { ssl: process.env.DATABASE_SSL === "disable" ? false : "require", max: 1 });
  try {
    const explicit = process.env.ORGANIZATION_ID?.trim();
    const rows = explicit
      ? await sql<ScriptOrganization[]>`select id, name from organizations where id = ${explicit} limit 1`
      : await sql<ScriptOrganization[]>`select id, name from organizations where metadata::jsonb ->> 'initial' = 'true' limit 1`;
    const org = rows[0];
    if (!org) {
      throw new Error(
        explicit
          ? `ORGANIZATION_ID ${explicit} matches no organization`
          : "No initial organization found (metadata.initial = true). Set ORGANIZATION_ID to the organization this script should run as.",
      );
    }
    console.log(`Running as organization ${org.name} (${org.id})`);
    return org;
  } finally {
    await sql.end({ timeout: 5 });
  }
}

/** Run `fn` as ORGANIZATION_ID, or as the initial organization when it is unset. */
export async function runScriptInOrganization<T>(fn: () => Promise<T>): Promise<T> {
  const org = await resolveScriptOrganization();
  const { runInOrganization } = await import("../../src/lib/tenancy/scope");
  return runInOrganization(org.id, fn);
}
