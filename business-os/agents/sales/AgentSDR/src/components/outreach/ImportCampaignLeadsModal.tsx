"use client";

import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import CampaignCsvMappingDialog from "@/components/leads/CampaignCsvMappingDialog";

type ImportResult = {
  total: number;
  imported: number;
  skippedSuppressed: number;
  skippedDuplicate: number;
  failed: { row: number; email: string; error: string }[];
};

/** Modal for bulk-importing leads into a campaign from a .csv/.xlsx file. */
export default function ImportCampaignLeadsModal({
  campaignId,
  onClose,
  onImported,
}: {
  campaignId: string;
  onClose: () => void;
  onImported: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  function handleImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a file first");
      return;
    }
    setError(null);
    setResult(null);
    setMappingFile(file);
  }

  if (mappingFile) {
    return <CampaignCsvMappingDialog
      file={mappingFile}
      endpoint={`/api/outreach/campaigns/${campaignId}/leads/import`}
      channel="email"
      onClose={() => setMappingFile(null)}
      onImported={(data) => {
        setResult(data as unknown as ImportResult);
        setMappingFile(null);
        onImported();
      }}
    />;
  }

  const modal = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-bg-white-0 rounded-2xl shadow-2xl w-full max-w-md p-6 z-10">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h2 className="text-base font-bold text-text-strong-950">Import Leads</h2>
            <p className="text-sm text-text-strong-950/60 mt-0.5">Upload a .csv or .xlsx file</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-strong-950/50 hover:bg-bg-weak-50 hover:text-text-strong-950/70 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="text-xs text-text-strong-950/45 mb-4">
          After selecting a file, map its columns to Email, name, company and other canonical fields.
          Unmapped columns remain available as template variables, and suppressed recipients are skipped.
        </p>

        <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-stroke-soft-200 rounded-xl px-4 py-8 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-500/30 transition-colors">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
          />
          <svg className="w-6 h-6 text-text-strong-950/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13.5V6.75m0 0l-3 3m3-3l3 3M6 20.25h12A2.25 2.25 0 0020.25 18v-9a2.25 2.25 0 00-2.25-2.25H15" />
          </svg>
          <span className="text-sm text-text-strong-950/60">{fileName ?? "Click to choose a file"}</span>
        </label>

        {error && <p className="text-xs text-red-600 dark:text-red-400 mt-3">{error}</p>}

        {result && (
          <div className="mt-4 rounded-lg bg-bg-weak-50 border border-stroke-soft-200 px-3 py-3 text-sm">
            <p className="text-text-strong-950">
              <span className="font-semibold">{result.total}</span> rows —{" "}
              <span className="text-emerald-700 dark:text-emerald-400 font-medium">{result.imported} imported</span>
              {result.skippedDuplicate > 0 && `, ${result.skippedDuplicate} duplicate`}
              {result.skippedSuppressed > 0 && (
                <>
                  , <span className="text-amber-700 dark:text-amber-400 font-medium">{result.skippedSuppressed} suppressed</span>
                </>
              )}
              {result.failed.length > 0 && (
                <>
                  , <span className="text-red-700 dark:text-red-400 font-medium">{result.failed.length} failed</span>
                </>
              )}
            </p>
            {result.failed.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1 max-h-32 overflow-y-auto">
                {result.failed.map((f) => (
                  <li key={f.row} className="text-xs text-red-600 dark:text-red-400">
                    Row {f.row} ({f.email || "unknown"}): {f.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex gap-3 mt-5">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-text-strong-950/70 border border-stroke-soft-200 rounded-lg hover:bg-bg-weak-50 transition-colors"
          >
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              onClick={handleImport}
              disabled={!fileName}
              className="flex-1 px-4 py-2.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Map columns
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
