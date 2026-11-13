"use client";

import dynamic from "next/dynamic";
import { RiLoader4Line } from "@remixicon/react";
import type { GridTable, GridWorkbook } from "@/lib/grid/schema";
import type { FolderCrumb } from "@/lib/grid/folders";
import type { SheetPayload } from "./WorkbookClient";

/**
 * Client wrapper so AG Grid can be loaded with ssr: false.
 *
 * Two reasons it is not imported directly by the page: `ssr: false` is illegal
 * inside a Server Component, and AG Grid measures DOM on mount, which makes
 * server rendering it pointless work at best. This also keeps its ~500KB out
 * of every other route's bundle.
 */
const WorkbookClient = dynamic(() => import("./WorkbookClient"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-text-soft-400">
      <RiLoader4Line className="size-5 animate-spin" />
    </div>
  ),
});

export default function GridLoader(props: {
  workbook: GridWorkbook;
  tables: GridTable[];
  breadcrumbs: FolderCrumb[];
  initialSheet: SheetPayload;
}) {
  return <WorkbookClient {...props} />;
}
