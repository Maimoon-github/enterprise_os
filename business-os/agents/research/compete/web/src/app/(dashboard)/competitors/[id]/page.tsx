import { promises as fs } from "fs";
import path from "path";

import { CompetitorDetail } from "./competitor-detail";

// In static (server-less) mode we prebuild one page per known competitor and
// disable the on-demand serverless fallback, so the whole app is static output
// with no functions. In live-backend mode we keep the fallback so competitors
// added through the API still resolve.
export const dynamicParams = process.env.NEXT_PUBLIC_STATIC_DATA !== "1";

export async function generateStaticParams(): Promise<{ id: string }[]> {
  // The baked competitor list is the source of truth at build time (it ships in
  // the repo under web/public). Read it directly so this works with no backend.
  try {
    const file = path.join(process.cwd(), "public", "api-static", "competitors.json");
    const raw = await fs.readFile(file, "utf-8");
    const competitors = JSON.parse(raw) as { id: string }[];
    return competitors.map((c) => ({ id: c.id }));
  } catch {
    // No baked data (e.g. pure live-backend build) - fall back to on-demand.
    return [];
  }
}

export default function CompetitorPage({ params }: { params: { id: string } }) {
  return <CompetitorDetail id={params.id} />;
}
