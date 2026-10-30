export function DiffViewer({ beforeText, afterText }: { beforeText: string; afterText: string }) {
  return (
    <div className="grid grid-cols-2 gap-4 text-xs font-mono">
      <div className="p-3 bg-red-950/20 border border-red-900/50 rounded text-red-300">
        <div className="font-bold mb-1">Previous Draft</div>
        {beforeText}
      </div>
      <div className="p-3 bg-emerald-950/20 border border-emerald-900/50 rounded text-emerald-300">
        <div className="font-bold mb-1">Reflexion Revised Draft</div>
        {afterText}
      </div>
    </div>
  );
}
