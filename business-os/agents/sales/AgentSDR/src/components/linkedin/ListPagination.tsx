import Link from "next/link";
import { RiArrowLeftSLine, RiArrowRightSLine } from "@remixicon/react";
import { PAGE_SIZE, totalPages } from "@/lib/linkedin/pagination";
import { cn } from "@/utils/cn";

type ListPaginationProps = {
  basePath: string;
  page: number;
  totalCount: number;
  className?: string;
};

const pageHref = (basePath: string, page: number) => (page <= 1 ? basePath : `${basePath}?page=${page}`);

/** 1 … 4 5 6 … 778 — the current page, its neighbours, and both ends. */
function pageWindow(page: number, pages: number): (number | "gap")[] {
  const wanted = new Set([1, pages, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pages));
  const sorted = [...wanted].sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  for (const p of sorted) {
    const prev = out[out.length - 1];
    if (typeof prev === "number" && p - prev > 1) out.push(p - prev === 2 ? prev + 1 : "gap");
    out.push(p);
  }
  return out;
}

const item =
  "flex h-8 min-w-8 items-center justify-center rounded-lg px-1.5 text-label-sm tabular-nums outline-none transition focus-visible:ring-2 focus-visible:ring-primary-base";

/**
 * The table footer used under server-paginated lists: "1–10 of 7,776" on the
 * left, previous / page numbers / next on the right. Put it inside the Frame,
 * after the FramePanel. Links, not buttons, so it works without client JS and
 * the page lives in the URL (`?page=n`).
 */
export const ListPagination = ({ basePath, page, totalCount, className }: ListPaginationProps) => {
  if (totalCount === 0) return null;
  const pages = totalPages(totalCount);
  const from = (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, totalCount);

  const nav = (target: number | null, label: string, Icon: typeof RiArrowLeftSLine) =>
    target ? (
      <Link href={pageHref(basePath, target)} aria-label={label} className={cn(item, "text-text-sub-600 hover:bg-bg-white-0 hover:text-text-strong-950")}>
        <Icon className="size-5" aria-hidden="true" />
      </Link>
    ) : (
      <span aria-disabled="true" aria-label={label} className={cn(item, "text-text-disabled-300")}>
        <Icon className="size-5" aria-hidden="true" />
      </span>
    );

  return (
    <nav aria-label="Pagination" className={cn("flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-3 pb-1 pt-2.5", className)}>
      <p className="text-paragraph-sm tabular-nums text-text-sub-600">
        {from.toLocaleString("en-US")}–{to.toLocaleString("en-US")} of {totalCount.toLocaleString("en-US")}
      </p>
      {pages > 1 && (
        <div className="flex items-center gap-1">
          {nav(page > 1 ? page - 1 : null, "Previous page", RiArrowLeftSLine)}
          <div className="hidden items-center gap-1 sm:flex">
            {pageWindow(page, pages).map((p, i) =>
              p === "gap" ? (
                <span key={`gap-${i}`} className="px-1 text-label-sm text-text-soft-400">
                  …
                </span>
              ) : p === page ? (
                <span key={p} aria-current="page" className={cn(item, "bg-bg-white-0 text-text-strong-950 shadow-regular-xs ring-1 ring-inset ring-stroke-soft-200")}>
                  {p.toLocaleString("en-US")}
                </span>
              ) : (
                <Link key={p} href={pageHref(basePath, p)} className={cn(item, "text-text-sub-600 hover:bg-bg-white-0 hover:text-text-strong-950")}>
                  {p.toLocaleString("en-US")}
                </Link>
              ),
            )}
          </div>
          <span className="px-2 text-paragraph-sm tabular-nums text-text-sub-600 sm:hidden">
            {page} / {pages}
          </span>
          {nav(page < pages ? page + 1 : null, "Next page", RiArrowRightSLine)}
        </div>
      )}
    </nav>
  );
};
