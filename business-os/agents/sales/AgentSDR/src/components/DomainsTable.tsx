"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import type { DomainsRow } from "@/lib/queries";
import ExportModal from "./ExportModal";
import { useNavigation } from "./NavigationProvider";

type Props = {
  data: DomainsRow[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
};

function fmt(val: string | null): string {
  if (!val) return "—";
  const n = parseFloat(val);
  if (isNaN(n)) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}


export default function DomainsTable({ data, total, page, pageSize, totalPages }: Props) {
  const { navigate } = useNavigation();
  const searchParams = useSearchParams();
  const [showExport, setShowExport] = useState(false);

  const goToPage = (p: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(p));
    navigate(`?${params.toString()}`);
  };

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const pages = (() => {
    const n = Math.min(7, totalPages);
    let s = Math.max(1, page - 3);
    const e = Math.min(totalPages, s + n - 1);
    s = Math.max(1, e - n + 1);
    return Array.from({ length: e - s + 1 }, (_, i) => s + i);
  })();

  return (
    <div className="flex flex-col gap-3 h-full min-h-0">
      {/* Count bar + Export */}
      <div className="flex items-center justify-between shrink-0">
        <p className="text-sm text-text-strong-950">
          Showing{" "}
          <span className="font-semibold text-text-strong-950">{start.toLocaleString()}–{end.toLocaleString()}</span>{" "}
          of <span className="font-semibold text-text-strong-950">{total.toLocaleString()}</span> companies
        </p>
        <button
          onClick={() => setShowExport(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-colors shadow-sm"
        >
          <svg className="w-4 h-4 text-indigo-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export CSV
        </button>
      </div>

      {showExport && (
        <ExportModal total={total} onClose={() => setShowExport(false)} />
      )}

      {/* Table wrapper */}
      <div className="flex-1 overflow-auto rounded-xl border border-stroke-soft-200 shadow-sm min-h-0">
        <table className="min-w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10">
            <tr className="bg-slate-900 text-slate-300">
              <th className="text-left px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap w-8">#</th>
              <th className="text-left px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap">Company</th>
              <th className="text-left px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap">Domain</th>
              <th className="text-left px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap">Category</th>
              <th className="text-left px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap">Country</th>
              <th className="text-right px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap">Annual Revenue</th>
              <th className="text-left px-4 py-3 font-medium text-xs tracking-wide whitespace-nowrap">Status</th>
            </tr>
          </thead>
          <tbody className="bg-bg-white-0">
            {data.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-20 text-center text-text-strong-950/50">
                  No results — try adjusting your filters.
                </td>
              </tr>
            ) : (
              data.map((row, i) => (
                <tr
                  key={row.domain}
                  className="border-t border-stroke-soft-200 hover:bg-indigo-50/40 dark:hover:bg-indigo-500/10 transition-colors"
                >
                  {/* # */}
                  <td className="px-4 py-3.5 text-text-strong-950/50 text-xs tabular-nums">{start + i}</td>

                  {/* Company */}
                  <td className="px-4 py-3.5">
                    <span className="font-semibold text-text-strong-950 truncate block max-w-52" title={row.merchantName ?? ""}>
                      {row.merchantName || <span className="text-text-strong-950/30 font-normal">—</span>}
                    </span>
                  </td>

                  {/* Domain */}
                  <td className="px-4 py-3.5">
                    {row.domainUrl ? (
                      <a
                        href={row.domainUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-500 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline truncate block text-xs max-w-48"
                        title={row.domain}
                      >
                        {row.domain}
                      </a>
                    ) : (
                      <span className="text-text-strong-950/60 truncate block text-xs max-w-48">{row.domain}</span>
                    )}
                  </td>

                  {/* Category */}
                  <td className="px-4 py-3.5">
                    {row.c1 ? (
                      <span
                        className="inline-flex items-center gap-1 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 text-xs px-2.5 py-1 rounded-full ring-1 ring-indigo-100 dark:ring-indigo-500/20 truncate max-w-48"
                        title={[row.c1, row.c2, row.c3].filter(Boolean).join(" › ")}
                      >
                        {row.c1}
                        {row.c2 && <><span className="text-indigo-300">›</span>{row.c2}</>}
                      </span>
                    ) : <span className="text-text-strong-950/30">—</span>}
                  </td>

                  {/* Country */}
                  <td className="px-4 py-3.5">
                    {row.countryCode
                      ? <span className="font-mono text-xs bg-bg-weak-50 text-text-strong-950/70 px-2 py-1 rounded ring-1 ring-stroke-soft-200">{row.countryCode}</span>
                      : <span className="text-text-strong-950/30">—</span>}
                  </td>

                  {/* Annual Revenue */}
                  <td className="px-4 py-3.5 text-right">
                    <span className="font-bold text-emerald-600 dark:text-emerald-400 tabular-nums text-sm">{fmt(row.annualSales)}</span>
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3.5">
                    {row.status ? (
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                        row.status === "Active"
                          ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200 dark:ring-emerald-500/30"
                          : "bg-bg-weak-50 text-text-strong-950/60 ring-1 ring-stroke-soft-200"
                      }`}>
                        {row.status}
                      </span>
                    ) : <span className="text-text-strong-950/30">—</span>}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between shrink-0">
          <button
            onClick={() => goToPage(page - 1)}
            disabled={page <= 1}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-text-strong-950/70 border border-stroke-soft-200 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-bg-weak-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Prev
          </button>

          <div className="flex items-center gap-1">
            {pages[0] > 1 && (
              <>
                <PageBtn p={1} current={page} onClick={goToPage} />
                {pages[0] > 2 && <span className="w-8 text-center text-text-strong-950/30 text-sm">…</span>}
              </>
            )}
            {pages.map((p) => <PageBtn key={p} p={p} current={page} onClick={goToPage} />)}
            {pages[pages.length - 1] < totalPages && (
              <>
                {pages[pages.length - 1] < totalPages - 1 && <span className="w-8 text-center text-text-strong-950/30 text-sm">…</span>}
                <PageBtn p={totalPages} current={page} onClick={goToPage} />
              </>
            )}
          </div>

          <button
            onClick={() => goToPage(page + 1)}
            disabled={page >= totalPages}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-text-strong-950/70 border border-stroke-soft-200 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-bg-weak-50 transition-colors"
          >
            Next
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
          </button>
        </div>
      )}
    </div>
  );
}

function PageBtn({ p, current, onClick }: { p: number; current: number; onClick: (p: number) => void }) {
  return (
    <button
      onClick={() => onClick(p)}
      className={`w-8 h-8 text-sm rounded-lg transition-colors ${
        p === current
          ? "bg-indigo-600 text-white font-semibold shadow-sm"
          : "text-text-strong-950/70 hover:bg-bg-weak-50 border border-stroke-soft-200"
      }`}
    >
      {p}
    </button>
  );
}
