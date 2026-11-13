import { authContextErrorResponse, requireOrgContext } from "@/lib/auth/context";
import { db } from "@/lib/db";
import { cleanDomains } from "@/lib/schema";
import { and, eq, gte, lte, isNull, isNotNull, desc, asc, sql } from "drizzle-orm";
import { NULL_CATEGORY } from "@/lib/queries";

export const dynamic = "force-dynamic";

function csvEscape(val: string | number | null | undefined): string {
  if (val === null || val === undefined) return "";
  const s = String(val);
  if (s.includes('"') || s.includes(",") || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export async function GET(request: Request) {
  // Global dataset: membership is required, but no organization scope is needed.
  try {
    await requireOrgContext(request);
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
  const { searchParams } = new URL(request.url);

  const countryCode = (searchParams.get("countryCode") ?? "US").toUpperCase();
  const c1 = searchParams.get("c1") ?? "";
  const c2 = searchParams.get("c2") ?? "";
  const c3 = searchParams.get("c3") ?? "";
  const platform = searchParams.get("platform") ?? "";
  const app = searchParams.get("app") ?? "";
  const minRevenue = searchParams.get("minRevenue") ?? "";
  const maxRevenue = searchParams.get("maxRevenue") ?? "";
  const sortBy = searchParams.get("sortBy") ?? "annualSales";
  const sortDir = searchParams.get("sortDir") ?? "desc";
  const limit = Math.min(50000, Math.max(1, parseInt(searchParams.get("limit") ?? "1000")));

  const conditions = [eq(cleanDomains.countryCode, countryCode)];

  if (c1 === NULL_CATEGORY) conditions.push(isNull(cleanDomains.c1));
  else if (c1) conditions.push(eq(cleanDomains.c1, c1));
  if (c2 === NULL_CATEGORY) conditions.push(isNull(cleanDomains.c2));
  else if (c2) conditions.push(eq(cleanDomains.c2, c2));
  if (c3 === NULL_CATEGORY) conditions.push(isNull(cleanDomains.c3));
  else if (c3) conditions.push(eq(cleanDomains.c3, c3));
  if (platform) conditions.push(eq(cleanDomains.platform, platform));
  if (app) conditions.push(sql`${cleanDomains.installedAppsArray} @> ARRAY[${app}]::text[]`);
  if (minRevenue || maxRevenue) {
    conditions.push(isNotNull(cleanDomains.annualSales));
    if (minRevenue) conditions.push(gte(cleanDomains.annualSales, minRevenue));
    if (maxRevenue) conditions.push(lte(cleanDomains.annualSales, maxRevenue));
  }

  const sortColumn =
    sortBy === "annualSales" ? cleanDomains.annualSales :
    sortBy === "rank" ? cleanDomains.rank :
    cleanDomains.domain;

  const orderBy =
    sortBy === "domain"
      ? (sortDir === "asc" ? asc(cleanDomains.domain) : desc(cleanDomains.domain))
      : sortDir === "asc"
      ? sql`${sortColumn} ASC NULLS LAST`
      : sql`${sortColumn} DESC NULLS LAST`;

  const rows = await db
    .select({
      domain: cleanDomains.domain,
      merchantName: cleanDomains.merchantName,
      platform: cleanDomains.platform,
      rank: cleanDomains.rank,
      countryCode: cleanDomains.countryCode,
      annualSales: cleanDomains.annualSales,
      categories: cleanDomains.categories,
      c1: cleanDomains.c1,
      c2: cleanDomains.c2,
      c3: cleanDomains.c3,
      installedAppsNames: cleanDomains.installedAppsNames,
      emails: cleanDomains.emails,
      phones: cleanDomains.phones,
    })
    .from(cleanDomains)
    .where(and(...conditions))
    .orderBy(orderBy)
    .limit(limit);

  const headers = [
    "Domain", "Merchant Name", "Platform", "Rank", "Country Code",
    "Annual Sales", "Categories", "Category L1", "Category L2", "Category L3",
    "Installed Apps", "Emails", "Phones",
  ];

  const csvRows = [
    headers.join(","),
    ...rows.map((r) =>
      [
        csvEscape(r.domain),
        csvEscape(r.merchantName),
        csvEscape(r.platform),
        csvEscape(r.rank),
        csvEscape(r.countryCode),
        csvEscape(r.annualSales),
        csvEscape(r.categories),
        csvEscape(r.c1),
        csvEscape(r.c2),
        csvEscape(r.c3),
        csvEscape(r.installedAppsNames),
        csvEscape(r.emails),
        csvEscape(r.phones),
      ].join(",")
    ),
  ];

  const csv = csvRows.join("\n");

  const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const parts = [
    countryCode,
    c1 === NULL_CATEGORY ? "uncategorized" : c1 ? slug(c1) : null,
    c2 ? slug(c2) : null,
    c3 ? slug(c3) : null,
    platform ? slug(platform) : null,
    app ? slug(app) : null,
    minRevenue ? `min${minRevenue}` : null,
    maxRevenue ? `max${maxRevenue}` : null,
    `${limit}rows`,
  ].filter(Boolean);
  const filename = `agentsdr-${parts.join("-")}.csv`;

  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
