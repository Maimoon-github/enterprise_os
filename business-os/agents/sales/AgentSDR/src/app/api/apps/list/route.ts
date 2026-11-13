import { db } from "@/lib/db";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const countryCode = (searchParams.get("countryCode") ?? "US").toUpperCase();

  const rows = await db.execute(sql`
    SELECT trim(app) AS app, COUNT(*)::int AS cnt
    FROM clean_domains,
    LATERAL regexp_split_to_table(installed_apps_names, ':') AS app
    WHERE country_code = ${countryCode}
      AND installed_apps_names IS NOT NULL
    GROUP BY trim(app)
    HAVING trim(app) != ''
    ORDER BY cnt DESC
    LIMIT 500
  `);

  const result: Record<string, number> = {};
  for (const row of rows as unknown as { app: string; cnt: number }[]) {
    if (row.app) result[row.app] = row.cnt;
  }

  return Response.json(result);
}
