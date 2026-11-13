import { NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import {
  createSearchBatch,
  listSearchBatches,
  startSearchBatchRun,
  type SearchUrlInput,
} from "@/lib/linkedin/searchBatches";
import type { SearchBatchKind } from "@/lib/linkedin/schema";

const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every((s) => typeof s === "string");

const isUrlRows = (v: unknown): v is { url: string; companyName?: string | null }[] =>
  Array.isArray(v) &&
  v.length > 0 &&
  v.every(
    (r) =>
      typeof r === "object" &&
      r !== null &&
      typeof (r as { url: unknown }).url === "string" &&
      ((r as { companyName?: unknown }).companyName === undefined ||
        (r as { companyName?: unknown }).companyName === null ||
        typeof (r as { companyName?: unknown }).companyName === "string")
  );

export async function GET(req: Request) {
  return withLinkedinOrg(req, async () => {
    try {
      const batches = await listSearchBatches();
      return NextResponse.json({ ok: true, batches });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}

export async function POST(req: Request) {
  return withLinkedinOrg(req, async () => {
    try {
      const body: unknown = await req.json();
      if (typeof body !== "object" || body === null) {
        return NextResponse.json({ ok: false, error: "Invalid request body" }, { status: 400 });
      }
      const { name, kind, urls, accountIds, run } = body as Record<string, unknown>;

      if (typeof name !== "string" || !name.trim()) {
        return NextResponse.json({ ok: false, error: "name is required" }, { status: 400 });
      }
      if (kind !== "SINGLE" && kind !== "BULK") {
        return NextResponse.json({ ok: false, error: 'kind must be "SINGLE" or "BULK"' }, { status: 400 });
      }
      if (!isUrlRows(urls)) {
        return NextResponse.json({ ok: false, error: "urls must be a non-empty array of { url, companyName? }" }, { status: 400 });
      }
      if (accountIds !== undefined && !isStringArray(accountIds)) {
        return NextResponse.json({ ok: false, error: "accountIds must be an array of strings" }, { status: 400 });
      }

      const rows: SearchUrlInput[] = urls.map((u) => ({ url: u.url, companyName: u.companyName ?? null }));

      let id: string;
      let queryCount: number;
      try {
        ({ id, queryCount } = await createSearchBatch({
          name,
          kind: kind as SearchBatchKind,
          accountIds: accountIds ?? [],
          rows,
        }));
      } catch (err) {
        if (err instanceof Error && (err.message === "No valid search URLs" || err.message === "Unknown account")) {
          return NextResponse.json({ ok: false, error: err.message }, { status: 400 });
        }
        throw err;
      }

      // Creating a search only queues it; `run: true` is opt-in. Starting on create
      // spent quota before the user had seen what was imported.
      const runResult = run === true ? await startSearchBatchRun(id) : null;

      return NextResponse.json({ ok: true, id, queryCount, run: runResult });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
