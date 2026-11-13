import { db } from "./db";
import { cleanDomains } from "./schema";
import { and, eq, gte, lte, desc, asc, isNotNull, isNull, count, sql } from "drizzle-orm";

export const NULL_CATEGORY = "__null__";

export type DomainsRow = {
  domain: string;
  merchantName: string | null;
  categories: string | null;
  c1: string | null;
  c2: string | null;
  c3: string | null;
  countryCode: string | null;
  annualSales: string | null;
  rank: number | null;
  platform: string | null;
  domainUrl: string;        // derived: https://{domain}
  status: string;           // always "Active" (clean_domains only has active stores)
};

export type DomainsResult = {
  data: DomainsRow[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  countryCode: string;
};

export type DomainsParams = {
  page?: string;
  pageSize?: string;
  countryCode?: string;
  c1?: string;
  c2?: string;
  c3?: string;
  platform?: string;
  app?: string;
  minRevenue?: string;
  maxRevenue?: string;
  sortBy?: string;
  sortDir?: string;
};

export async function getDomains(params: DomainsParams): Promise<DomainsResult> {
  const page = Math.max(1, parseInt(params.page ?? "1"));
  const pageSize = Math.min(50, Math.max(5, parseInt(params.pageSize ?? "20")));
  const countryCode = (params.countryCode ?? "US").toUpperCase();
  const c1 = params.c1 ?? "";
  const c2 = params.c2 ?? "";
  const c3 = params.c3 ?? "";
  const platform = params.platform ?? "";
  const app = params.app ?? "";
  const minRevenue = params.minRevenue ?? "";
  const maxRevenue = params.maxRevenue ?? "";
  const sortBy = params.sortBy ?? "annualSales";
  const sortDir = params.sortDir ?? "desc";

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

  const where = and(...conditions);

  const sortColumn =
    sortBy === "annualSales" ? cleanDomains.annualSales :
    sortBy === "rank"        ? cleanDomains.rank :
    cleanDomains.domain;

  const orderBy =
    sortBy === "domain"
      ? (sortDir === "asc" ? asc(cleanDomains.domain) : desc(cleanDomains.domain))
      : sortDir === "asc"
      ? sql`${sortColumn} ASC NULLS LAST`
      : sql`${sortColumn} DESC NULLS LAST`;

  const hasExtraFilters = c1 || c2 || c3 || platform || app || minRevenue || maxRevenue;

  const [rows, totalResult] = await Promise.all([
    db
      .select({
        domain: cleanDomains.domain,
        merchantName: cleanDomains.merchantName,
        categories: cleanDomains.categories,
        c1: cleanDomains.c1,
        c2: cleanDomains.c2,
        c3: cleanDomains.c3,
        countryCode: cleanDomains.countryCode,
        annualSales: cleanDomains.annualSales,
        rank: cleanDomains.rank,
        platform: cleanDomains.platform,
      })
      .from(cleanDomains)
      .where(where)
      .orderBy(orderBy)
      .limit(pageSize)
      .offset((page - 1) * pageSize),

    hasExtraFilters
      ? db.select({ count: count() }).from(cleanDomains).where(where)
      : db.select({ count: count() }).from(cleanDomains).where(eq(cleanDomains.countryCode, countryCode)),
  ]);

  const total = Number(totalResult[0].count);

  const data: DomainsRow[] = rows.map((r) => ({
    ...r,
    domainUrl: `https://${r.domain}`,
    status: "Active",
  }));

  return { data, total, page, pageSize, totalPages: Math.ceil(total / pageSize), countryCode };
}
