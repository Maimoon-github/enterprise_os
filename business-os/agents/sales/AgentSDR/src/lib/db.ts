import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import * as schema from "./schema";

// Credentials come from DATABASE_URL — never hardcode them here. The
// scripts/ migrations read the same variable, so the app and the schema
// tooling always point at the same database.
//
// The client is created on first use, not when this module loads: `next
// build` loads every route to collect page data, and a build must not need
// database credentials (the Docker build context carries no .env). A
// missing DATABASE_URL still fails loudly — at the first query.

function createDb() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set — copy .env.example to .env.local and fill it in");
  }

  /**
   * Pool size is deliberately small and configurable.
   *
   * This is now the app's ONLY pool — the LinkedIn half used to run a second
   * one through Prisma, which is what made the 50-connection ceiling on the
   * Azure server easy to hit. When it is exhausted every query in the app
   * fails at once with "remaining connection slots are reserved for roles with
   * the SUPERUSER attribute", so keep DB_POOL_MAX well under 50 across all
   * running instances — a rolling deploy briefly runs two containers.
   */
  const client = postgres(connectionString, {
    ssl: process.env.DATABASE_SSL === "disable" ? false : "require",
    max: Number(process.env.DB_POOL_MAX ?? 8),
    idle_timeout: 20,
  });
  return drizzle(client, { schema });
}

type Db = ReturnType<typeof createDb>;
let instance: Db | undefined;

/** The one Drizzle instance, created on first property access. */
export const db: Db = new Proxy({} as Db, {
  get(_, prop) {
    instance ??= createDb();
    const value = Reflect.get(instance, prop, instance);
    return typeof value === "function" ? value.bind(instance) : value;
  },
});
