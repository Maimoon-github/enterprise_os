/**
 * Drizzle client for the LinkedIn tables.
 *
 * Deliberately re-exports the SAME `db` the rest of the app uses rather than
 * opening a second pool. The Azure server allows only 50 connections in
 * total; the whole point of retiring Prisma was to stop this process holding
 * two independent pools against it.
 *
 * Import `db` from here in LinkedIn code so the dependency reads clearly,
 * and the LinkedIn tables so call sites get one import instead of two.
 */

export { db } from "@/lib/db";
export * from "./schema";
