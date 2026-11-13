import { db } from "@/lib/db";
import { cleanDomains } from "@/lib/schema";
import { and, eq, isNotNull, count, asc } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const countryCode = (searchParams.get("countryCode") ?? "US").toUpperCase();
  const level = searchParams.get("level") ?? "c1";
  const c1 = searchParams.get("c1") ?? "";
  const c2 = searchParams.get("c2") ?? "";

  let rows: { value: string | null; count: unknown }[] = [];

  if (level === "c1") {
    rows = await db
      .select({ value: cleanDomains.c1, count: count() })
      .from(cleanDomains)
      .where(and(eq(cleanDomains.countryCode, countryCode), isNotNull(cleanDomains.c1)))
      .groupBy(cleanDomains.c1)
      .orderBy(asc(cleanDomains.c1));
  } else if (level === "c2" && c1) {
    rows = await db
      .select({ value: cleanDomains.c2, count: count() })
      .from(cleanDomains)
      .where(and(eq(cleanDomains.countryCode, countryCode), eq(cleanDomains.c1, c1), isNotNull(cleanDomains.c2)))
      .groupBy(cleanDomains.c2)
      .orderBy(asc(cleanDomains.c2));
  } else if (level === "c3" && c1 && c2) {
    rows = await db
      .select({ value: cleanDomains.c3, count: count() })
      .from(cleanDomains)
      .where(and(eq(cleanDomains.countryCode, countryCode), eq(cleanDomains.c1, c1), eq(cleanDomains.c2, c2), isNotNull(cleanDomains.c3)))
      .groupBy(cleanDomains.c3)
      .orderBy(asc(cleanDomains.c3));
  }

  const result: Record<string, number> = {};
  for (const row of rows) {
    if (row.value) result[row.value] = Number(row.count);
  }
  return Response.json(result);
}
