"use client";

import type { ReactNode } from "react";
import { RiArrowDownLine, RiArrowUpDownLine, RiArrowUpLine } from "@remixicon/react";
import * as Table from "@/components/alignui/table";
import { cn } from "@/utils/cn";
import type { Direction } from "./leadTypes";

/** Header cell shared by both tables, with an optional sort button. */
export function SortableHead({ label, sortKey, activeSort, direction, onSort, className }: {
  label: ReactNode;
  sortKey?: string;
  activeSort?: string;
  direction?: Direction;
  onSort?: (key: string) => void;
  className?: string;
}) {
  const active = Boolean(sortKey) && sortKey === activeSort;
  const Icon = active ? (direction === "asc" ? RiArrowUpLine : RiArrowDownLine) : RiArrowUpDownLine;
  return (
    <Table.Head
      scope="col"
      aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : sortKey ? "none" : undefined}
      className={cn("whitespace-nowrap px-4 py-2.5", className)}
    >
      {sortKey && onSort ? (
        <button type="button" onClick={() => onSort(sortKey)} className={cn("inline-flex items-center gap-1.5 rounded outline-none transition hover:text-text-strong-950 focus-visible:ring-2 focus-visible:ring-stroke-strong-950", active && "text-text-strong-950")}>
          {label}
          <Icon className={cn("size-3.5", active ? "text-text-strong-950" : "text-text-soft-400")} aria-hidden="true" />
        </button>
      ) : label}
    </Table.Head>
  );
}

/** Body cell padding, matching the header. */
export const cellClass = "px-4";

/**
 * Fixed layout: columns take the widths their headers declare instead of
 * growing to the longest name on the page; long values truncate.
 */
export const fixedTableStyle = { tableLayout: "fixed", minWidth: 900 } as const;
