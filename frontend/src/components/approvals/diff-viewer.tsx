interface DiffViewerProps {
  beforeText?: string;
  afterText?: string;
  beforeTitle?: string;
  afterTitle?: string;
}

export function DiffViewer({
  beforeText = "Draft 1 (Initial Creative Plan)",
  afterText = "Draft 2 (Reflexion Revised Blueprint)",
  beforeTitle = "Previous Blueprint",
  afterTitle = "Reflexion Revised Draft",
}: DiffViewerProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
      <div className="p-4 bg-rose-950/20 border border-rose-900/40 rounded-lg text-rose-200 space-y-2">
        <div className="font-semibold text-rose-400 text-xs uppercase tracking-wider flex items-center justify-between">
          <span>{beforeTitle}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-950 border border-rose-800 text-rose-300">
            Original
          </span>
        </div>
        <pre className="whitespace-pre-wrap font-sans text-xs text-rose-100/90 leading-relaxed overflow-x-auto">
          {beforeText}
        </pre>
      </div>

      <div className="p-4 bg-emerald-950/20 border border-emerald-900/40 rounded-lg text-emerald-200 space-y-2">
        <div className="font-semibold text-emerald-400 text-xs uppercase tracking-wider flex items-center justify-between">
          <span>{afterTitle}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300">
            Proposed Revision
          </span>
        </div>
        <pre className="whitespace-pre-wrap font-sans text-xs text-emerald-100/90 leading-relaxed overflow-x-auto">
          {afterText}
        </pre>
      </div>
    </div>
  );
}
